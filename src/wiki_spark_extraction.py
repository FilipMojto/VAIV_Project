"""Distributed extraction of BGG-related pages from a Wikipedia XML dump."""

import csv
import html
import re
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    IntegerType,
    StringType,
    StructField,
    StructType,
)

from src.title_matching import build_title_match_index


# Lightweight extraction: inspect only the page header before parsing full XML.
_TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.DOTALL)
_NAMESPACE_PATTERN = re.compile(r"<ns>(.*?)</ns>", re.DOTALL)


OUTPUT_SCHEMA = StructType([
    StructField("wiki_page_id", StringType(), nullable=False),
    StructField("wiki_title", StringType(), nullable=False),
    StructField("wiki_namespace", IntegerType(), nullable=False),
    StructField("wiki_text", StringType(), nullable=True),
    StructField("app_id", StringType(), nullable=False),
    StructField("game_title", StringType(), nullable=False),
    StructField("matched_variant", StringType(), nullable=False),
    StructField("variant_type", StringType(), nullable=False),
])


def extract_matching_wikipedia_pages(
    spark: SparkSession,
    bgg_tsv_path: str | Path,
    wiki_dump_path: str | Path,
    output_path: str | Path,
    split_max_size: int = 32 * 1024 * 1024,
    overwrite: bool = False,
    progress_callback=None,
):
    """
    Extract Wikipedia pages matching BGG primary or alternate titles.

    The Wikipedia dump is processed through Spark's Hadoop XmlInputFormat,
    allowing Spark to distribute splittable BZip2 input across partitions.

    Matching pages are parsed into structured records and written to Parquet.
    Each output row represents one BGG-game/Wikipedia-page association.

    Returns:
        A DataFrame reading the resulting Parquet dataset.
    """

    bgg_tsv_path = Path(bgg_tsv_path).resolve()
    wiki_dump_path = Path(wiki_dump_path).resolve()
    output_path = Path(output_path).resolve()

    if not bgg_tsv_path.is_file():
        raise FileNotFoundError(bgg_tsv_path)

    if not wiki_dump_path.is_file():
        raise FileNotFoundError(wiki_dump_path)

    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}. "
            "Use overwrite=True only if replacement is intended."
        )

    # ---------------------------------------------------------
    # 1. Build the BGG title index on the driver.
    # ---------------------------------------------------------
    with bgg_tsv_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        bgg_records = list(
            csv.DictReader(file, delimiter="\t")
        )

    title_index = build_title_match_index(bgg_records)

    print("=== BGG TITLE INDEX ===")
    print(f"BGG games: {len(bgg_records):,}")
    print(f"Unique title keys: {len(title_index):,}")

    # ---------------------------------------------------------
    # 2. Make helper modules available to Python workers.
    # ---------------------------------------------------------
    project_root = Path(__file__).resolve().parent.parent
    spark.sparkContext.addPyFile(
        str(project_root / "src" / "title_matching.py")
    )
    spark.sparkContext.addPyFile(
        str(project_root / "src" / "wiki_extraction.py")
    )

    # ---------------------------------------------------------
    # 3. Broadcast the title index.
    # ---------------------------------------------------------
    title_index_broadcast = spark.sparkContext.broadcast(title_index)

    completed_partitions = spark.sparkContext.accumulator(0)
    matched_pages = spark.sparkContext.accumulator(0)

    # ---------------------------------------------------------
    # 4. Read the Wikipedia dump using Spark's XML InputFormat.
    # ---------------------------------------------------------
    hadoop_conf = {
        "xmlinput.start": "<page>",
        "xmlinput.end": "</page>",
        "xmlinput.encoding": "UTF-8",
        "mapreduce.input.fileinputformat.split.maxsize": str(
            split_max_size
        ),
    }

    wikipedia_records = spark.sparkContext.newAPIHadoopFile(
        str(wiki_dump_path),
        "org.apache.spark.sql.execution.datasources.xml.XmlInputFormat",
        "org.apache.hadoop.io.LongWritable",
        "org.apache.hadoop.io.Text",
        conf=hadoop_conf,
    )

    total_partitions = wikipedia_records.getNumPartitions()

    if progress_callback is not None:
        progress_callback(
            total_partitions,
            completed_partitions,
            matched_pages,
    )

    print(f"Wikipedia input partitions: {total_partitions}")

    # ---------------------------------------------------------
    # 5. Match pages on Spark workers.
    # ---------------------------------------------------------

    def process_partition(partition):
        from title_matching import normalize_title
        from wiki_extraction import parse_wikipedia_page

        index = title_index_broadcast.value

        for _, page_xml in partition:
            if isinstance(page_xml, bytes):
                page_xml = page_xml.decode("utf-8")

            title_match = _TITLE_PATTERN.search(page_xml)
            namespace_match = _NAMESPACE_PATTERN.search(page_xml)

            if title_match is None or namespace_match is None:
                continue

            try:
                namespace = int(namespace_match.group(1))
            except ValueError:
                continue

            # Only Wikipedia's main article namespace.
            if namespace != 0:
                continue

            # XML entities in the title must be decoded before matching.
            wiki_title = html.unescape(title_match.group(1))

            normalized_title = normalize_title(wiki_title)
            game_matches = index.get(normalized_title)

            # Avoid full XML parsing for unrelated pages.
            if not game_matches:
                continue

            page = parse_wikipedia_page(page_xml)

            if page is None:
                continue

            # Count this matching Wikipedia page once.
            matched_pages.add(1)

            for game_match in game_matches:
                yield (
                    page["wiki_page_id"],
                    page["wiki_title"],
                    page["wiki_namespace"],
                    page["wiki_text"],
                    game_match["app_id"],
                    game_match["game_title"],
                    game_match["matched_variant"],
                    game_match["variant_type"],
                )

        # Reached the end of this partition successfully.
        completed_partitions.add(1)


    matched_records = wikipedia_records.mapPartitions(
        process_partition
    )

    # ---------------------------------------------------------
    # 6. Create a structured DataFrame and persist to Parquet.
    # ---------------------------------------------------------
    matched_df = spark.createDataFrame(
        matched_records,
        schema=OUTPUT_SCHEMA,
    )

    save_mode = "overwrite" if overwrite else "error"
    matched_df.write.mode(save_mode).parquet(str(output_path))

    print(f"Parquet output written to: {output_path}")

    # Return a DataFrame backed by the saved data. Subsequent
    # operations will read Parquet, not process Wikipedia again.
    result_df = spark.read.parquet(str(output_path))

    return result_df, {
        "completed_partitions": completed_partitions,
        "matched_pages": matched_pages,
    }
