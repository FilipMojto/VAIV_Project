
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
import time
from pyspark.sql import SparkSession
from tqdm import tqdm

from src.wiki_spark_extraction import extract_matching_wikipedia_pages


project_root = Path(__file__).resolve().parents[2]

bgg_path = project_root / "data/bgg_games/bgg_games_deduplicated_20261121_003935.tsv"
wiki_path = project_root / "data/wiki/enwiki-latest-pages-articles.xml.bz2"
# output_path = project_root / "data/wiki_extracted/bgg_wikipedia_matches"
output_path = project_root / "data/wiki_extracted/bgg_wikipedia_matches_expanded"

spark = (
    SparkSession.builder
    .appName("BGG-Wikipedia-Extraction")
    .master("local[4]")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

# Shared references populated by the extraction function.
progress_info = {}
progress_ready = Event()


def capture_progress(total, completed, matched):
    """Receive progress counters before the Spark extraction starts."""
    progress_info["total"] = total
    progress_info["completed"] = completed
    progress_info["matched"] = matched
    progress_ready.set()


def run_extraction():
    """Run the Spark extraction in a background thread."""
    return extract_matching_wikipedia_pages(
        spark=spark,
        bgg_tsv_path=str(bgg_path),
        wiki_dump_path=str(wiki_path),
        output_path=str(output_path),
        split_max_size=32 * 1024 * 1024,
        overwrite=False,
        progress_callback=capture_progress,
    )


try:
    print("\n=== STARTING FULL WIKIPEDIA EXTRACTION ===")
    print(f"BGG input: {bgg_path}")
    print(f"Wikipedia dump: {wiki_path}")
    print(f"Output: {output_path}")

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_extraction)

        # Wait until the extraction function supplies its counters.
        while not progress_ready.is_set() and not future.done():
            progress_ready.wait(timeout=0.2)

        # If extraction failed before supplying progress information,
        # this propagates the original exception.
        if future.done() and not progress_ready.is_set():
            result, accumulators = future.result()

        else:
            total_partitions = progress_info["total"]
            completed_accumulator = progress_info["completed"]
            matched_accumulator = progress_info["matched"]

            previous_completed = 0

            with tqdm(
                total=total_partitions,
                desc="Wikipedia extraction",
                unit="partition",
                dynamic_ncols=True,
            ) as progress_bar:

                while not future.done():
                    completed = min(
                        completed_accumulator.value,
                        total_partitions,
                    )

                    matched = matched_accumulator.value

                    # tqdm expects an increment, not a cumulative value.
                    progress_bar.update(
                        max(0, completed - previous_completed)
                    )
                    previous_completed = max(
                        previous_completed,
                        completed,
                    )

                    progress_bar.set_postfix(
                        matched_pages=matched
                    )

                    time.sleep(1.0)

                # Retrieve the result and propagate any worker exception.
                result, accumulators = future.result()

                # Capture the final accumulator values.
                completed = min(
                    accumulators["completed_partitions"].value,
                    total_partitions,
                )

                matched = accumulators["matched_pages"].value

                progress_bar.update(
                    max(0, completed - previous_completed)
                )
                progress_bar.set_postfix(
                    matched_pages=matched
                )

    print("\n=== EXTRACTION COMPLETED ===")
    print("Output schema:")
    result.printSchema()

    row_count = result.count()

    print(f"Extracted match rows: {row_count}")
    print(f"Matched Wikipedia pages: {accumulators['matched_pages'].value}")
    print(f"Completed partitions: {accumulators['completed_partitions'].value}")
    print(f"Parquet output: {output_path}")

finally:
    spark.stop()
