import bz2
import csv
import tempfile
from pathlib import Path

from pyspark.sql import SparkSession

from src.wiki_spark_extraction import (
    extract_matching_wikipedia_pages,
    extract_wikipedia_fields,
)

progress_info = {}

def capture_progress(total, completed, matched):
    progress_info["total"] = total
    progress_info["completed"] = completed
    progress_info["matched"] = matched

def make_page(page_id, title, namespace, text):
    return f"""
    <page>
        <title>{title}</title>
        <ns>{namespace}</ns>
        <id>{page_id}</id>
        <revision>
            <id>{page_id + 10000}</id>
            <text>{text}</text>
        </revision>
    </page>
    """


def main():
    with tempfile.TemporaryDirectory(prefix="bgg_wiki_test_") as temp_dir:
        temp_path = Path(temp_dir)

        bgg_path = temp_path / "bgg_test.tsv"
        wiki_path = temp_path / "wiki_test.xml.bz2"
        output_path = temp_path / "output"

        # Three BGG records. Two games share the same alternate title.
        bgg_records = [
            {
                "app_id": "13",
                "game_title": "Catan",
                "alternate_names": "The Settlers of Catan",
            },
            {
                "app_id": "999",
                "game_title": "Another Catan Game",
                "alternate_names": "The Settlers of Catan",
            },
            {
                "app_id": "822",
                "game_title": "Carcassonne",
                "alternate_names": "",
            },
        ]

        with bgg_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "app_id",
                    "game_title",
                    "alternate_names",
                ],
                delimiter="\t",
            )
            writer.writeheader()
            writer.writerows(bgg_records)

        # Synthetic Wikipedia dump.
        pages = [
            make_page(
                1001,
                "The Settlers of Catan",
                0,
                """Catan is a multiplayer board game.

                {{Infobox game
                | publication history = First edition 1995; second edition 2001
                | players = 3–4
                | setup time = 10 minutes
                | random chance = Dice rolling
                | website = https://example.com
                }}
                """,
            ),
            make_page(
                1002,
                "Carcassonne",
                0,
                "Carcassonne is a tile-placement board game.",
            ),
            make_page(
                1003,
                "Category:The Settlers of Catan",
                14,
                "This is a category page.",
            ),
            make_page(
                1004,
                "Unrelated Article",
                0,
                "This article is unrelated to the BGG dataset.",
            ),
        ]

        xml_content = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">'
            + "".join(pages)
            + "</mediawiki>"
        )

        with bz2.open(wiki_path, "wt", encoding="utf-8") as file:
            file.write(xml_content)

        spark = (
            SparkSession.builder
            .appName("Synthetic-BGG-Wikipedia-Integration-Test")
            .master("local[2]")
            .getOrCreate()
        )
        spark.sparkContext.setLogLevel("WARN")

        try:
            print("\n=== RUNNING SYNTHETIC INTEGRATION TEST ===")

            result, accumulators = extract_matching_wikipedia_pages(
                spark=spark,
                bgg_tsv_path=str(bgg_path),
                wiki_dump_path=str(wiki_path),
                output_path=str(output_path),
                split_max_size=1024 * 1024,
                overwrite=False,
                progress_callback=capture_progress,
            )

            print("\n=== EXTRACTED DATA ===")
            result.select(
                "wiki_page_id",
                "wiki_title",
                "app_id",
                "game_title",
                "matched_variant",
                "variant_type",
            ).orderBy("wiki_page_id", "app_id").show(
                truncate=False
            )

            rows = result.collect()

            print("\n=== OUTPUT VALIDATION ===")

            assert len(rows) == 3, (
                f"Expected 3 rows, got {len(rows)}"
            )

            page_ids = {row.wiki_page_id for row in rows}
            assert page_ids == {"1001", "1002"}, (
                f"Unexpected Wikipedia page IDs: {page_ids}"
            )

            catan_rows = [
                row for row in rows
                if row.wiki_page_id == "1001"
            ]

            assert len(catan_rows) == 2, (
                "The shared Catan title should match two BGG games"
            )

            carcassonne_rows = [
                row for row in rows
                if row.wiki_page_id == "1002"
            ]

            assert len(carcassonne_rows) == 1

            assert all(
                row.wiki_namespace == 0 for row in rows
            ), "Non-main-namespace page was included"

            assert all(
                row.wiki_text is not None for row in rows
            ), "Expected article text to be present"

            print("Output rows: 3")
            print("Distinct Wikipedia pages: 2")
            print("Distinct BGG games: 3")
            print("Namespace filtering: passed")
            print("Shared-title matching: passed")
            print("Article-text extraction: passed")

            # These counters must be exposed by the extraction function.
            print("\n=== ACCUMULATOR VALIDATION ===")

            completed = accumulators["completed_partitions"].value
            matched = accumulators["matched_pages"].value

            print(f"Completed partitions: {completed}")
            print(f"Matched Wikipedia pages: {matched}")

            assert completed > 0, (
                "No completed partitions were recorded"
            )

            assert matched == 2, (
                f"Expected 2 matched pages, got {matched}"
            )

            assert progress_info["total"] == 1
            assert progress_info["completed"] is accumulators["completed_partitions"]
            assert progress_info["matched"] is accumulators["matched_pages"]

            print("Progress callback: passed")

            print("\n=== ALL INTEGRATION ASSERTIONS PASSED ===")
            print("\n=== WIKIPEDIA FIELD ENRICHMENT ===")

            enriched_path = temp_path / "enriched"

            enriched = extract_wikipedia_fields(
                spark=spark,
                input_path=output_path,
                output_path=enriched_path,
            )

            enriched_rows = enriched.collect()

            assert len(enriched_rows) == 3

            enriched_catan = [
                row for row in enriched_rows
                if row.wiki_page_id == "1001"
            ]

            assert len(enriched_catan) == 2

            for row in enriched_catan:
                assert row.publication_history == (
                    "First edition 1995; second edition 2001"
                )
                assert row.number_of_players == "3–4"
                assert row.setup_time == "10 minutes"
                assert row.chance == "Dice rolling"
                assert row.official_website == "https://example.com"

            print("Publication history: passed")
            print("Number of players: passed")
            print("Setup time: passed")
            print("Chance: passed")
            print("Official website: passed")
            print("Fields preserved across shared-title associations: passed")

        finally:
            spark.stop()


if __name__ == "__main__":
    main()
