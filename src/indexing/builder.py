
"""Build a persistent SQLite inverted index from a BGG TSV dataset."""

import csv
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from src.data_schema import EXPECTED_FIELDS
from src.indexing.database import SCHEMA, SCHEMA_VERSION, SQLiteIndex
from src.indexing.tokenizer import TOKENIZER_PATTERN, tokenize_text

INDEXED_FIELDS = (
    "game_title",
    "alternate_names",
    "short_description",
    "description",
    "game_type",
    "game_category",
    "game_mechanic",
    "game_family",
    "designer",
    "publisher",
    "awards_honors",
)


POSTINGS_BATCH_SIZE = 5000


class SQLiteIndexBuilder:
    """Build a persistent BGG inverted index in SQLite."""

    @staticmethod
    def _sha256_file(path: Path) -> str:
        """Calculate a file's SHA-256 hash."""

        digest = hashlib.sha256()

        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)

        return digest.hexdigest()

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text using the shared tokenizer."""

        return tokenize_text(text)

    def build(
        self,
        source_path: Path,
        database_path: Path,
    ) -> dict[str, object]:
        """Build a SQLite index from a validated TSV source."""

        source_path = Path(source_path)
        database_path = Path(database_path)

        if not source_path.is_file():
            raise FileNotFoundError(
                f"Source TSV does not exist: {source_path}"
            )

        if source_path.resolve() == database_path.resolve():
            raise ValueError("Source and database paths must be different.")

        database_path.parent.mkdir(parents=True, exist_ok=True)

        source_hash_before = self._sha256_file(source_path)

        # Create the temporary database in the destination directory.
        # This allows os.replace() to publish it atomically.
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{database_path.name}.",
            suffix=".tmp",
            dir=database_path.parent,
        )
        os.close(file_descriptor)

        temporary_path = Path(temporary_name)
        connection = None

        try:
            connection = sqlite3.connect(temporary_path)
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(SCHEMA)
            connection.execute("BEGIN")
            connection.execute("PRAGMA defer_foreign_keys = ON")

            term_ids: dict[str, int] = {}
            term_frequencies: dict[str, int] = {}
            postings_batch: list[tuple[str, int, int]] = []

            document_count = 0
            posting_count = 0
            seen_ids: set[str] = set()

            with source_path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as source:
                reader = csv.reader(source, delimiter="\t", strict=True)

                header = next(reader, None)

                if tuple(header or ()) != EXPECTED_FIELDS:
                    raise ValueError(
                        "Source TSV header does not match the expected "
                        "43-column schema."
                    )

                for row in reader:
                    line_number = reader.line_num

                    if len(row) != len(EXPECTED_FIELDS):
                        raise ValueError(
                            f"Invalid row width at line {line_number}: "
                            f"expected {len(EXPECTED_FIELDS)}, got {len(row)}."
                        )

                    record = dict(zip(EXPECTED_FIELDS, row))

                    app_id = record["app_id"]
                    game_title = record["game_title"]

                    if not app_id or not app_id.isdigit() or int(app_id) <= 0:
                        raise ValueError(
                            f"Invalid app_id at line {line_number}: "
                            f"{app_id!r}."
                        )

                    if app_id in seen_ids:
                        raise ValueError(
                            f"Duplicate app_id at line {line_number}: "
                            f"{app_id!r}."
                        )

                    if not game_title.strip():
                        raise ValueError(
                            f"Missing game_title at line {line_number} "
                            f"for app_id {app_id!r}."
                        )

                    seen_ids.add(app_id)

                    connection.execute(
                        """
                        INSERT INTO documents (
                            app_id,
                            game_title,
                            designer,
                            publisher
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            app_id,
                            game_title,
                            record["designer"],
                            record["publisher"],
                        ),
                    )

                    combined_text = " ".join(
                        record[field] or ""
                        for field in INDEXED_FIELDS
                    )

                    document_terms = Counter(
                        self._tokenize(combined_text)
                    )

                    for term, frequency in document_terms.items():
                        if term not in term_ids:
                            term_ids[term] = len(term_ids) + 1
                            term_frequencies[term] = 0

                        term_frequencies[term] += 1

                        postings_batch.append(
                            (app_id, term_ids[term], frequency)
                        )

                    if len(postings_batch) >= POSTINGS_BATCH_SIZE:
                        connection.executemany(
                            """
                            INSERT INTO postings (
                                app_id,
                                term_id,
                                term_frequency
                            )
                            VALUES (?, ?, ?)
                            """,
                            postings_batch,
                        )

                        posting_count += len(postings_batch)
                        postings_batch.clear()

                    document_count += 1

            if document_count == 0:
                raise ValueError("Source TSV contains no game records.")

            if postings_batch:
                connection.executemany(
                    """
                    INSERT INTO postings (
                        app_id,
                        term_id,
                        term_frequency
                    )
                    VALUES (?, ?, ?)
                    """,
                    postings_batch,
                )

                posting_count += len(postings_batch)

            connection.executemany(
                """
                INSERT INTO terms (
                    term_id,
                    term,
                    document_frequency
                )
                VALUES (?, ?, ?)
                """,
                (
                    (term_ids[term], term, frequency)
                    for term, frequency in term_frequencies.items()
                ),
            )

            # Make sure the source was not modified while being indexed.
            source_hash_after = self._sha256_file(source_path)

            if source_hash_before != source_hash_after:
                raise RuntimeError(
                    "Source TSV changed during index construction."
                )

            metadata = {
                "schema_version": SCHEMA_VERSION,
                "source_filename": source_path.name,
                "source_sha256": source_hash_after,
                "document_count": str(document_count),
                "term_count": str(len(term_ids)),
                "posting_count": str(posting_count),
                "indexed_fields": json.dumps(INDEXED_FIELDS),
                "tokenizer_pattern": TOKENIZER_PATTERN,
                "tokenizer_description": (
                    "Lowercase text; ASCII alphabetic tokens "
                    "with at least three characters."
                ),
                "created_at": datetime.now().astimezone().isoformat(),
            }

            connection.executemany(
                """
                INSERT INTO index_metadata (key, value)
                VALUES (?, ?)
                """,
                metadata.items(),
            )

            connection.commit()

            # Validate the completed temporary database.
            integrity_result = connection.execute(
                "PRAGMA integrity_check"
            ).fetchall()

            if integrity_result != [("ok",)]:
                raise RuntimeError(
                    f"SQLite integrity check failed: {integrity_result}"
                )

            foreign_key_errors = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            if foreign_key_errors:
                raise RuntimeError(
                    f"SQLite foreign-key check failed: "
                    f"{foreign_key_errors[:5]}"
                )

            connection.close()
            connection = None

            with SQLiteIndex(temporary_path) as index:
                stats = index.get_collection_stats()

                if (
                    stats["document_count"] != document_count
                    or stats["term_count"] != len(term_ids)
                    or stats["posting_count"] != posting_count
                ):
                    raise RuntimeError(
                        "Database statistics do not match build results."
                    )

            # Publish only after the database has passed validation.
            os.replace(temporary_path, database_path)

            return {
                "database": str(database_path),
                "source": source_path.name,
                "source_sha256": source_hash_after,
                "document_count": document_count,
                "term_count": len(term_ids),
                "posting_count": posting_count,
            }

        finally:
            if connection is not None:
                connection.close()

            if temporary_path.exists():
                temporary_path.unlink()
