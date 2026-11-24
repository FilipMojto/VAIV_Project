
"""Run the complete BGG–Wikipedia enrichment pipeline with Apache Spark.

Existing intermediate Parquet datasets are reused automatically. Missing
stages are generated and saved without overwriting existing data.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
import time

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from tqdm import tqdm

from src.wiki_spark_extraction import (
    extract_matching_wikipedia_pages,
    resolve_wikipedia_redirects,
    extract_wikipedia_fields,
    rank_wikipedia_candidates,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BGG_PATH = (
    PROJECT_ROOT
    / "data/bgg_games/bgg_games_deduplicated_20261121_003935.tsv"
)
DEFAULT_WIKI_PATH = (
    PROJECT_ROOT
    / "data/wiki/enwiki-latest-pages-articles.xml.bz2"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data/wiki_extracted"

FIELD_NAMES = (
    "short_description",
    "infobox_type",
    "designer",
    "publisher",
    "release_date",
    "number_of_players",
    "playing_time",
    "publication_history",
    "setup_time",
    "chance",
    "official_website",
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the complete BGG–Wikipedia Spark pipeline."
    )

    parser.add_argument(
        "--bgg",
        type=Path,
        default=DEFAULT_BGG_PATH,
        help="Input BGG TSV dataset.",
    )
    parser.add_argument(
        "--wiki",
        type=Path,
        default=DEFAULT_WIKI_PATH,
        help="Input Wikipedia XML dump.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for intermediate and final Parquet datasets.",
    )
    parser.add_argument(
        "--master",
        default="local[4]",
        help="Spark master (default: local[4]).",
    )
    parser.add_argument(
        "--split-max-size",
        type=int,
        default=32 * 1024 * 1024,
        help="Maximum Wikipedia XML split size in bytes.",
    )

    return parser.parse_args()


def dataset_exists(path):
    """Check whether a Spark Parquet dataset already exists."""
    return Path(path).exists()


def load_or_create_dataset(spark, path, stage_name, create):
    """Reuse an existing dataset or create it without overwriting."""

    path = Path(path)

    if dataset_exists(path):
        print(f"\n=== REUSING {stage_name.upper()} ===")
        print(f"Dataset: {path}")
        return spark.read.parquet(str(path))

    print(f"\n=== RUNNING {stage_name.upper()} ===")

    result = create()

    # Stage functions persist their output themselves.
    if not dataset_exists(path):
        raise RuntimeError(
            f"{stage_name} completed without creating its output: {path}"
        )

    return result


def run_matching_with_progress(
    spark,
    bgg_path,
    wiki_path,
    output_path,
    split_max_size,
):
    """Run the expensive Wikipedia matching stage with progress reporting."""

    progress_info = {}
    progress_ready = Event()

    def capture_progress(total, completed, matched):
        progress_info["total"] = total
        progress_info["completed"] = completed
        progress_info["matched"] = matched
        progress_ready.set()

    def run_extraction():
        return extract_matching_wikipedia_pages(
            spark=spark,
            bgg_tsv_path=str(bgg_path),
            wiki_dump_path=str(wiki_path),
            output_path=str(output_path),
            split_max_size=split_max_size,
            overwrite=False,
            progress_callback=capture_progress,
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_extraction)

        while not progress_ready.is_set() and not future.done():
            progress_ready.wait(timeout=0.2)

        if future.done() and not progress_ready.is_set():
            result, accumulators = future.result()

        else:
            total = progress_info["total"]
            completed_accumulator = progress_info["completed"]
            matched_accumulator = progress_info["matched"]

            previous_completed = 0

            with tqdm(
                total=total,
                desc="Wikipedia extraction",
                unit="partition",
                dynamic_ncols=True,
            ) as progress:

                while not future.done():
                    completed = min(
                        completed_accumulator.value,
                        total,
                    )

                    matched = matched_accumulator.value

                    progress.update(
                        max(0, completed - previous_completed)
                    )
                    previous_completed = max(
                        previous_completed,
                        completed,
                    )

                    progress.set_postfix(matched_pages=matched)
                    time.sleep(1.0)

                result, accumulators = future.result()

                completed = min(
                    accumulators["completed_partitions"].value,
                    total,
                )

                progress.update(
                    max(0, completed - previous_completed)
                )
                progress.set_postfix(
                    matched_pages=accumulators["matched_pages"].value
                )

    print(
        "Matched pages:",
        accumulators["matched_pages"].value,
    )
    print(
        "Completed partitions:",
        accumulators["completed_partitions"].value,
    )

    return result


def read_bgg_dataset(spark, path):
    """Read the original BGG TSV while preserving its string columns."""

    if not path.is_file():
        raise FileNotFoundError(
            f"BGG input dataset does not exist: {path}"
        )

    dataframe = (
        spark.read
        .option("header", "true")
        .option("sep", "\t")
        .option("inferSchema", "false")
        .csv(str(path))
    )

    if "app_id" not in dataframe.columns:
        raise ValueError("BGG input does not contain app_id.")

    if "game_title" not in dataframe.columns:
        raise ValueError("BGG input does not contain game_title.")

    return dataframe


def build_enriched_dataset(
    spark,
    bgg_path,
    ranked_path,
    output_path,
):
    """Join the best Wikipedia candidate onto every original BGG record."""

    bgg_df = read_bgg_dataset(spark, bgg_path)
    ranked_df = spark.read.parquet(str(ranked_path))

    # Only one selected candidate should exist per BGG game.
    selected_df = ranked_df.filter(
        F.col("is_best_candidate") == True
    )

    duplicate_candidates = (
        selected_df
        .groupBy("app_id")
        .count()
        .filter(F.col("count") > 1)
        .limit(1)
        .count()
    )

    if duplicate_candidates:
        raise ValueError(
            "The ranked dataset contains multiple selected candidates "
            "for at least one app_id."
        )

    # Map the original candidate and the article used as evidence
    # separately. For resolved redirects, evidence_* refers to the
    # redirect target article.
    wiki_columns = [
        F.col("app_id"),
        F.col("wiki_page_id").alias("wiki_matched_page_id"),
        F.col("wiki_title").alias("wiki_matched_title"),
        F.col("evidence_wiki_page_id").alias("wiki_page_id"),
        F.col("evidence_wiki_title").alias("wiki_title"),
        F.col("variant_type").alias("wiki_matched_variant_type"),
        F.col("redirect_status").alias("wiki_redirect_status"),
        F.col("candidate_score").alias("wiki_candidate_score"),
    ]

    wiki_field_mapping = {
        "short_description": "wiki_short_description",
        "infobox_type": "wiki_infobox_type",
        "designer": "wiki_designer",
        "publisher": "wiki_publisher",
        "release_date": "wiki_release_date",
        "number_of_players": "wiki_number_of_players",
        "playing_time": "wiki_playing_time",
        "publication_history": "wiki_publication_history",
        "setup_time": "wiki_setup_time",
        "chance": "wiki_chance",
        "official_website": "wiki_official_website",
    }

    for source_name, target_name in wiki_field_mapping.items():
        wiki_columns.append(
            F.col(f"evidence_{source_name}").alias(target_name)
        )

    selected_wiki_df = selected_df.select(*wiki_columns)

    # Check that the original BGG dataset has unique join keys.
    duplicate_bgg_ids = (
        bgg_df
        .groupBy("app_id")
        .count()
        .filter(F.col("count") > 1)
        .limit(1)
        .count()
    )

    if duplicate_bgg_ids:
        raise ValueError(
            "The original BGG dataset contains duplicate app_id values."
        )

    # Avoid silently replacing existing Wikipedia columns.
    conflicts = sorted(
        set(bgg_df.columns) & set(selected_wiki_df.columns) - {"app_id"}
    )

    if conflicts:
        raise ValueError(
            f"BGG input already contains Wikipedia columns: {conflicts}"
        )

    enriched_df = bgg_df.join(
        selected_wiki_df,
        on="app_id",
        how="left",
    )

    # Validate the result before writing it.
    original_count = bgg_df.count()
    enriched_count = enriched_df.count()

    if original_count != enriched_count:
        raise RuntimeError(
            "The final left join changed the BGG record count: "
            f"{original_count} -> {enriched_count}"
        )

    enriched_duplicates = (
        enriched_df
        .groupBy("app_id")
        .count()
        .filter(F.col("count") > 1)
        .limit(1)
        .count()
    )

    if enriched_duplicates:
        raise RuntimeError(
            "The final enriched dataset contains duplicate app_id values."
        )

    enriched_df.write.mode("error").parquet(str(output_path))

    print(f"Final enriched dataset written to: {output_path}")

    return spark.read.parquet(str(output_path))


def print_final_statistics(dataframe):
    """Report final integration and attribute-coverage statistics."""

    total = dataframe.count()

    matched = dataframe.filter(
        F.col("wiki_matched_page_id").isNotNull()
    )

    matched_count = matched.count()

    unique_pages = (
        matched
        .select("wiki_page_id")
        .distinct()
        .count()
    )

    print("\n=== FINAL ENRICHMENT STATISTICS ===")
    print(f"Total BGG records: {total:,}")
    print(f"Records with Wikipedia data: {matched_count:,}")
    print(f"Records without Wikipedia data: {total - matched_count:,}")
    print(f"Distinct Wikipedia target pages: {unique_pages:,}")

    print("\n=== WIKIPEDIA ATTRIBUTE COVERAGE ===")

    for field in FIELD_NAMES:
        column = f"wiki_{field}"

        count = matched.filter(
            F.col(column).isNotNull()
            & (F.trim(F.col(column)) != "")
        ).count()

        percentage = (
            count / matched_count * 100
            if matched_count
            else 0
        )

        print(
            f"{column}: {count:,} / {matched_count:,} "
            f"({percentage:.1f}%)"
        )


def main():
    args = parse_args()

    bgg_path = args.bgg.resolve()
    wiki_path = args.wiki.resolve()
    output_dir = args.output_dir.resolve()

    if not bgg_path.is_file():
        raise FileNotFoundError(bgg_path)

    matches_path = output_dir / "bgg_wikipedia_matches_expanded"
    redirects_path = output_dir / "bgg_wikipedia_redirects"
    fields_path = output_dir / "bgg_wikipedia_fields_v5"
    ranked_path = output_dir / "bgg_wikipedia_ranked_v3"
    enriched_path = output_dir / "bgg_wikipedia_enriched_v3"

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== BGG–WIKIPEDIA SPARK PIPELINE ===")
    print(f"BGG input: {bgg_path}")
    print(f"Wikipedia dump: {wiki_path}")
    print(f"Output directory: {output_dir}")

    spark = (
        SparkSession.builder
        .appName("BGG-Wikipedia-Full-Pipeline")
        .master(args.master)
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    try:
        # -----------------------------------------------------
        # 1. Candidate matching
        # -----------------------------------------------------
        matches_df = load_or_create_dataset(
            spark,
            matches_path,
            "Wikipedia candidate matching",
            lambda: run_matching_with_progress(
                spark,
                bgg_path,
                wiki_path,
                matches_path,
                args.split_max_size,
            ),
        )

        print(f"Candidate associations: {matches_df.count():,}")

        # -----------------------------------------------------
        # 2. Redirect resolution
        # -----------------------------------------------------
        redirects_df = load_or_create_dataset(
            spark,
            redirects_path,
            "Redirect resolution",
            lambda: resolve_wikipedia_redirects(
                spark=spark,
                input_path=matches_path,
                output_path=redirects_path,
                overwrite=False,
            ),
        )

        print(f"Redirect records: {redirects_df.count():,}")

        # -----------------------------------------------------
        # 3. Wikipedia attribute extraction
        # -----------------------------------------------------
        fields_df = load_or_create_dataset(
            spark,
            fields_path,
            "Wikipedia attribute extraction",
            lambda: extract_wikipedia_fields(
                spark=spark,
                input_path=matches_path,
                output_path=fields_path,
                overwrite=False,
            ),
        )

        print(f"Extracted associations: {fields_df.count():,}")

        # -----------------------------------------------------
        # 4. Candidate ranking
        # -----------------------------------------------------
        ranked_df = load_or_create_dataset(
            spark,
            ranked_path,
            "Candidate ranking",
            lambda: rank_wikipedia_candidates(
                spark=spark,
                matches_path=matches_path,
                fields_path=fields_path,
                redirects_path=redirects_path,
                output_path=ranked_path,
                overwrite=False,
            ),
        )

        print(f"Ranked associations: {ranked_df.count():,}")

        # -----------------------------------------------------
        # 5. Final BGG–Wikipedia integration
        # -----------------------------------------------------
        enriched_df = load_or_create_dataset(
            spark,
            enriched_path,
            "Final BGG enrichment",
            lambda: build_enriched_dataset(
                spark,
                bgg_path,
                ranked_path,
                enriched_path,
            ),
        )

        print_final_statistics(enriched_df)

        print("\n=== PIPELINE COMPLETED SUCCESSFULLY ===")
        print(f"Final dataset: {enriched_path}")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
