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
from pyspark.sql import Window
from pyspark.sql import functions as F
from pyspark.sql.functions import udf

from src.wiki_extraction import (
    build_wikipedia_title_index,
    resolve_redirect_target,
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

REDIRECT_OUTPUT_SCHEMA = StructType([
    StructField("wiki_page_id", StringType(), nullable=False),
    StructField("wiki_title", StringType(), nullable=False),
    StructField("redirect_target", StringType(), nullable=True),
    StructField("redirect_status", StringType(), nullable=False),
    StructField("redirect_target_page_id", StringType(), nullable=True),
])


GAME_FIELDS_SCHEMA = StructType([
    StructField("short_description", StringType(), nullable=True),
    StructField("infobox_type", StringType(), nullable=True),
    StructField("designer", StringType(), nullable=True),
    StructField("publisher", StringType(), nullable=True),
    StructField("release_date", StringType(), nullable=True),
    StructField("number_of_players", StringType(), nullable=True),
    StructField("playing_time", StringType(), nullable=True),
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



def resolve_wikipedia_redirects(
    spark: SparkSession,
    input_path: str | Path,
    output_path: str | Path,
    overwrite: bool = False,
):
    """
    Resolve direct Wikipedia redirects among previously extracted pages.

    Each distinct Wikipedia page is processed once. The original
    association dataset remains unchanged.

    Returns:
        A DataFrame reading the resulting page-level Parquet dataset.
    """

    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()

    if not input_path.exists():
        raise FileNotFoundError(input_path)

    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}. "
            "Use overwrite=True only if replacement is intended."
        )

    # ---------------------------------------------------------
    # 1. Read the extracted associations and deduplicate pages.
    # ---------------------------------------------------------
    pages_df = (
        spark.read.parquet(str(input_path))
        .select("wiki_page_id", "wiki_title", "wiki_text")
        .dropDuplicates(["wiki_page_id"])
    )

    # ---------------------------------------------------------
    # 2. Extract redirect targets using a Spark UDF.
    # ---------------------------------------------------------
    # Make the helper module available to Spark workers.
    helper_path = Path(__file__).resolve().parent / "wiki_extraction.py"
    spark.sparkContext.addPyFile(str(helper_path))

    def extract_target(text):
        from wiki_extraction import extract_redirect_target

        return extract_redirect_target(text)

    extract_target_udf = udf(
        extract_target,
        StringType(),
    )

    pages_with_targets = pages_df.withColumn(
        "redirect_target",
        extract_target_udf("wiki_text"),
    )

    # Collect only page metadata, not the article text.
    pages = [
        {
            "wiki_page_id": row["wiki_page_id"],
            "wiki_title": row["wiki_title"],
            "redirect_target": row["redirect_target"],
        }
        for row in pages_with_targets.select(
            "wiki_page_id",
            "wiki_title",
            "redirect_target",
        ).collect()
    ]

    print(f"Distinct Wikipedia pages: {len(pages):,}")

    # ---------------------------------------------------------
    # 3. Build a title index from all extracted pages.
    # ---------------------------------------------------------
    title_index = build_wikipedia_title_index(pages)

    # ---------------------------------------------------------
    # 4. Resolve each redirect.
    # ---------------------------------------------------------
    resolved_records = []

    for page in pages:
        target = page["redirect_target"]

        if target is None:
            redirect_status = "not_redirect"
            target_page_id = None
        else:
            resolution = resolve_redirect_target(
                target,
                title_index,
            )
            redirect_status = resolution["redirect_status"]
            target_page_id = resolution["redirect_target_page_id"]

        resolved_records.append((
            page["wiki_page_id"],
            page["wiki_title"],
            target,
            redirect_status,
            target_page_id,
        ))

    # ---------------------------------------------------------
    # 5. Create and persist the page-level results.
    # ---------------------------------------------------------
    result_df = spark.createDataFrame(
        resolved_records,
        schema=REDIRECT_OUTPUT_SCHEMA,
    )

    save_mode = "overwrite" if overwrite else "error"

    result_df.write.mode(save_mode).parquet(str(output_path))

    print(f"Redirect resolution output written to: {output_path}")

    return spark.read.parquet(str(output_path))


def extract_wikipedia_fields(
    spark: SparkSession,
    input_path: str | Path,
    output_path: str | Path,
    overwrite: bool = False,
):
    """
    Extract selected game attributes from previously matched Wikipedia pages.

    Fields are extracted once per distinct Wikipedia page and joined
    back to the original BGG-Wikipedia associations.

    Returns:
        A DataFrame reading the enriched Parquet dataset.
    """

    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()

    if not input_path.exists():
        raise FileNotFoundError(input_path)

    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}. "
            "Use overwrite=True only if replacement is intended."
        )

    helper_path = Path(__file__).resolve().parent / "wiki_extraction.py"
    spark.sparkContext.addPyFile(str(helper_path))

    def extract_fields(text):
        from wiki_extraction import extract_wikipedia_game_fields
        return extract_wikipedia_game_fields(text)

    extract_fields_udf = udf(extract_fields, GAME_FIELDS_SCHEMA)

    # Read the original association data.
    associations_df = spark.read.parquet(str(input_path))

    # Extract once per distinct Wikipedia page.
    unique_pages_df = (
        associations_df
        .select("wiki_page_id", "wiki_text")
        .dropDuplicates(["wiki_page_id"])
    )

    fields_df = (
        unique_pages_df
        .withColumn("_fields", extract_fields_udf("wiki_text"))
        .select("wiki_page_id", "_fields.*")
    )

    # Restore all original BGG-Wikipedia associations.
    enriched_df = associations_df.join(
        fields_df,
        on="wiki_page_id",
        how="left",
    )

    save_mode = "overwrite" if overwrite else "error"
    enriched_df.write.mode(save_mode).parquet(str(output_path))

    print(f"Enriched dataset written to: {output_path}")

    return spark.read.parquet(str(output_path))


def rank_wikipedia_candidates(
    spark: SparkSession,
    matches_path: str | Path,
    fields_path: str | Path,
    redirects_path: str | Path,
    output_path: str | Path,
    overwrite: bool = False,
):
    """
    Rank Wikipedia candidates for each BGG game using title and
    extracted article metadata.

    Resolved redirects use the target article's metadata as ranking
    evidence, while preserving the original candidate information.

    All candidate associations are retained in the output.

    Returns:
        A DataFrame reading the ranked Parquet dataset.
    """

    matches_path = Path(matches_path).resolve()
    fields_path = Path(fields_path).resolve()
    redirects_path = Path(redirects_path).resolve()
    output_path = Path(output_path).resolve()

    for input_path in (
        matches_path,
        fields_path,
        redirects_path,
    ):
        if not input_path.exists():
            raise FileNotFoundError(input_path)

    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}. "
            "Use overwrite=True only if replacement is intended."
        )

    # ---------------------------------------------------------
    # 1. Read the three previously generated datasets.
    # ---------------------------------------------------------
    matches_df = spark.read.parquet(str(matches_path))
    fields_df = spark.read.parquet(str(fields_path))
    redirects_df = spark.read.parquet(str(redirects_path))

    field_names = [
        "short_description",
        "infobox_type",
        "designer",
        "publisher",
        "release_date",
        "number_of_players",
        "playing_time",
    ]

    # Keep one metadata record per Wikipedia page.
    unique_fields_df = (
        fields_df
        .select("wiki_page_id", "wiki_title", *field_names)
        .dropDuplicates(["wiki_page_id"])
    )

    # ---------------------------------------------------------
    # 2. Attach the candidate article's own extracted fields.
    # ---------------------------------------------------------
    candidate_fields_df = unique_fields_df.select(
        "wiki_page_id",
        *[
            F.col(name).alias(f"candidate_{name}")
            for name in field_names
        ],
    )

    candidates_df = (
        matches_df
        .join(
            candidate_fields_df,
            on="wiki_page_id",
            how="left",
        )
    )

    # ---------------------------------------------------------
    # 3. Attach redirect resolution information.
    # ---------------------------------------------------------
    redirect_info_df = redirects_df.select(
        "wiki_page_id",
        "redirect_target",
        "redirect_status",
        "redirect_target_page_id",
    )

    candidates_df = candidates_df.join(
        redirect_info_df,
        on="wiki_page_id",
        how="left",
    )

    # ---------------------------------------------------------
    # 4. Look up metadata belonging to redirect targets.
    # ---------------------------------------------------------
    target_fields_df = unique_fields_df.select(
        F.col("wiki_page_id").alias("_target_page_id"),
        F.col("wiki_title").alias("target_wiki_title"),
        *[
            F.col(name).alias(f"target_{name}")
            for name in field_names
        ],
    )

    candidates_df = candidates_df.join(
        target_fields_df,
        F.col("redirect_target_page_id")
        == F.col("_target_page_id"),
        how="left",
    )

    # Use target metadata when available. Otherwise, use the
    # candidate article's own metadata.
    candidates_df = candidates_df.withColumn(
        "evidence_wiki_page_id",
        F.coalesce(
            F.col("redirect_target_page_id"),
            F.col("wiki_page_id"),
        ),
    ).withColumn(
        "evidence_wiki_title",
        F.coalesce(
            F.col("target_wiki_title"),
            F.col("wiki_title"),
        ),
    )

    for name in field_names:
        candidates_df = candidates_df.withColumn(
            f"evidence_{name}",
            F.coalesce(
                F.col(f"target_{name}"),
                F.col(f"candidate_{name}"),
            ),
        )

    # ---------------------------------------------------------
    # 5. Calculate transparent scoring components.
    # ---------------------------------------------------------

    # Title variant score.
    candidates_df = candidates_df.withColumn(
        "title_variant_score",
        F.when(F.col("variant_type") == "primary_board_game", 5)
        .when(F.col("variant_type") == "alternate_board_game", 4)
        .when(F.col("variant_type") == "primary_game", 3)
        .when(F.col("variant_type") == "alternate_game", 2)
        .when(F.col("variant_type") == "primary", 1)
        .otherwise(0),
    )

    description = F.lower(
        F.coalesce(
            F.col("evidence_short_description"),
            F.lit(""),
        )
    )

    candidates_df = candidates_df.withColumn(
        "description_score",
        F.when(description.contains("board game"), 5)
        .when(description.contains("game"), 2)
        .otherwise(0),
    )

    infobox_type = F.lower(
        F.coalesce(
            F.col("evidence_infobox_type"),
            F.lit(""),
        )
    )

    candidates_df = candidates_df.withColumn(
        "infobox_score",
        F.when(infobox_type == "game", 4)
        .otherwise(0),
    )

    # Total heuristic score.
    candidates_df = candidates_df.withColumn(
        "candidate_score",
        F.col("title_variant_score")
        + F.col("description_score")
        + F.col("infobox_score"),
    )

    # ---------------------------------------------------------
    # 6. Rank candidates independently for each BGG game.
    # ---------------------------------------------------------
    ranking_window = (
        Window
        .partitionBy("app_id")
        .orderBy(
            F.desc("candidate_score"),
            F.when(
                F.col("redirect_status") == "resolved", 1
            ).otherwise(0).asc(),
            F.col("wiki_title").asc(),
            F.col("wiki_page_id").asc(),
        )
    )

    ranked_df = (
        candidates_df
        .withColumn(
            "candidate_rank",
            F.row_number().over(ranking_window),
        )
        .withColumn(
            "is_best_candidate",
            F.col("candidate_rank") == 1,
        )
    )

    # Remove internal join columns, keeping the original candidate,
    # its metadata, redirect information, and ranking evidence.
    internal_columns = [
        "_target_page_id",
        "target_wiki_title",
        *[f"target_{name}" for name in field_names],
    ]

    ranked_df = ranked_df.drop(*internal_columns)

    # ---------------------------------------------------------
    # 7. Persist the ranked associations.
    # ---------------------------------------------------------
    save_mode = "overwrite" if overwrite else "error"

    ranked_df.write.mode(save_mode).parquet(
        str(output_path)
    )

    print(f"Ranked candidate dataset written to: {output_path}")

    return spark.read.parquet(str(output_path))
