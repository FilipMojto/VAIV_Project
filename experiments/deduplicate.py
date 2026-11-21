"""Create a versioned BGG dataset with unique app_id values."""

import argparse
import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from src.config import BGG_GAMES_DIR
from src.versioning import SmartVersioner
from src.data_schema import EXPECTED_FIELDS


SOURCE_STEM = "bgg_games"
OUTPUT_STEM = "bgg_games_deduplicated"
EXTENSION = ".tsv"


def sha256_file(path: Path) -> str:
    """Calculate a file's SHA-256 fingerprint."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deduplicate(source: Path, destination: Path) -> dict:
    """Keep the first occurrence of each app_id and write a new TSV."""
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            writer = csv.writer(
                temporary_file,
                delimiter="\t",
                lineterminator="\n",
            )

            seen = {}
            duplicate_ids = []
            conflicting_ids = []
            source_rows = 0
            unique_rows = 0

            with source.open(
                "r", encoding="utf-8-sig", newline=""
            ) as source_file:
                reader = csv.reader(source_file, delimiter="\t", strict=True)
                header = next(reader, None)

                if header is None:
                    raise ValueError("Source TSV is empty.")

                if tuple(header) != EXPECTED_FIELDS:
                    raise ValueError(
                        "Source header does not match the expected 43-column schema."
                    )

                app_id_index = header.index("app_id")
                writer.writerow(header)

                for row_number, row in enumerate(reader, start=2):
                    source_rows += 1

                    if len(row) != len(header):
                        raise ValueError(
                            f"Row {row_number}: expected {len(header)} fields, "
                            f"found {len(row)}."
                        )

                    app_id = row[app_id_index].strip()

                    if not app_id:
                        raise ValueError(
                            f"Row {row_number}: app_id is empty."
                        )

                    if not app_id.isdigit() or int(app_id) <= 0:
                        raise ValueError(
                            f"Row {row_number}: invalid app_id {app_id!r}."
                        )

                    if app_id in seen:
                        duplicate_ids.append(app_id)

                        if seen[app_id] != row and app_id not in conflicting_ids:
                            conflicting_ids.append(app_id)

                        continue

                    seen[app_id] = row
                    writer.writerow(row)
                    unique_rows += 1

        if source_rows != unique_rows + len(duplicate_ids):
            raise RuntimeError("Row-count verification failed.")

        if unique_rows != len(seen):
            raise RuntimeError("Unique-ID verification failed.")

        source_hash = sha256_file(source)
        output_hash = sha256_file(temporary_path)

        os.replace(temporary_path, destination)
        temporary_path = None

        return {
            "source": source.name,
            "output": destination.name,
            "source_sha256": source_hash,
            "output_sha256": output_hash,
            "source_rows": source_rows,
            "unique_rows": unique_rows,
            "removed_duplicates": len(duplicate_ids),
            "duplicate_ids": sorted(set(duplicate_ids), key=int),
            "conflicting_duplicate_ids": sorted(
                conflicting_ids, key=int
            ),
            "created_at": datetime.now().astimezone().isoformat(),
            "duplicate_policy": "Keep first occurrence of each app_id",
        }

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create a versioned deduplicated BGG dataset."
    )
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        help="Source TSV; defaults to the latest original snapshot.",
    )
    args = parser.parse_args(argv)

    try:
        source = args.source

        if source is None:
            source_versioner = SmartVersioner(
                SOURCE_STEM, BGG_GAMES_DIR, EXTENSION
            )
            source = source_versioner.get_latest_match()

        if source is None or not source.is_file():
            raise FileNotFoundError("No source BGG TSV found.")

        output_versioner = SmartVersioner(
            OUTPUT_STEM, BGG_GAMES_DIR, EXTENSION
        )
        destination = output_versioner.get_next_save_file()

        report = deduplicate(source, destination)

        report_path = destination.with_suffix(".json")
        temporary_report = report_path.with_suffix(".json.tmp")

        try:
            temporary_report.write_text(
                json.dumps(report, indent=4, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_report, report_path)
        finally:
            temporary_report.unlink(missing_ok=True)

        print("Deduplication completed.")
        print(f"Source: {source}")
        print(f"Output: {destination}")
        print(f"Report: {report_path}")
        print(f"Source rows: {report['source_rows']:,}")
        print(f"Unique rows: {report['unique_rows']:,}")
        print(f"Removed duplicates: {report['removed_duplicates']:,}")
        print(f"Duplicate IDs: {report['duplicate_ids']}")
        print(
            f"Conflicting duplicate IDs: "
            f"{report['conflicting_duplicate_ids']}"
        )

        return 0

    except Exception as exc:
        print(f"Deduplication failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
