
"""SQLite storage for the persistent BGG inverted index."""

import sqlite3
from pathlib import Path


SCHEMA_VERSION = "1"


SCHEMA = """
CREATE TABLE documents (
    app_id TEXT PRIMARY KEY,
    game_title TEXT NOT NULL,
    designer TEXT,
    publisher TEXT
);

CREATE TABLE terms (
    term_id INTEGER PRIMARY KEY,
    term TEXT NOT NULL UNIQUE,
    document_frequency INTEGER NOT NULL
        CHECK (document_frequency > 0)
);

CREATE TABLE postings (
    app_id TEXT NOT NULL,
    term_id INTEGER NOT NULL,
    term_frequency INTEGER NOT NULL
        CHECK (term_frequency > 0),

    PRIMARY KEY (app_id, term_id),

    FOREIGN KEY (app_id)
        REFERENCES documents(app_id)
        ON DELETE CASCADE,

    FOREIGN KEY (term_id)
        REFERENCES terms(term_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_postings_term_id
    ON postings(term_id);

CREATE TABLE index_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class SQLiteIndex:
    """Connection and basic access to a persistent BGG index."""

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)

        if not self.database_path.is_file():
            raise FileNotFoundError(
                f"SQLite index does not exist: {self.database_path}"
            )

        self.connection = sqlite3.connect(self.database_path)
        self.connection.execute("PRAGMA foreign_keys = ON")

        self._validate_schema()

    def _validate_schema(self) -> None:
        """Validate the schema version and required table columns."""

        expected_columns = {
            "documents": {
                "app_id",
                "game_title",
                "designer",
                "publisher",
            },
            "terms": {
                "term_id",
                "term",
                "document_frequency",
            },
            "postings": {
                "app_id",
                "term_id",
                "term_frequency",
            },
            "index_metadata": {
                "key",
                "value",
            },
        }

        try:
            result = self.connection.execute(
                """
                SELECT value
                FROM index_metadata
                WHERE key = 'schema_version'
                """
            ).fetchone()

            if result is None:
                raise ValueError(
                    "SQLite index is missing its schema version."
                )

            if result[0] != SCHEMA_VERSION:
                raise ValueError(
                    f"Unsupported index schema version: {result[0]!r}. "
                    f"Expected {SCHEMA_VERSION!r}."
                )

            existing_tables = {
                row[0]
                for row in self.connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                )
            }

            for table, required_columns in expected_columns.items():
                if table not in existing_tables:
                    raise ValueError(
                        f"SQLite index is missing table {table!r}."
                    )

                actual_columns = {
                    row[1]
                    for row in self.connection.execute(
                        f"PRAGMA table_info({table})"
                    )
                }

                missing_columns = required_columns - actual_columns

                if missing_columns:
                    raise ValueError(
                        f"Table {table!r} is missing columns: "
                        f"{', '.join(sorted(missing_columns))}."
                    )

        except sqlite3.Error as exc:
            self.close()
            raise ValueError(
                "File is not a valid BGG SQLite index."
            ) from exc

        except ValueError:
            self.close()
            raise

    def get_metadata(self) -> dict[str, str]:
        """Return all index metadata as a dictionary."""

        rows = self.connection.execute(
            "SELECT key, value FROM index_metadata"
        )

        return dict(rows)


    def get_document(self, app_id: str) -> dict[str, str | None] | None:
        """Retrieve document metadata by BGG application ID."""

        row = self.connection.execute(
            """
            SELECT app_id, game_title, designer, publisher
            FROM documents
            WHERE app_id = ?
            """,
            (str(app_id),),
        ).fetchone()

        if row is None:
            return None

        return {
            "app_id": row[0],
            "game_title": row[1],
            "designer": row[2],
            "publisher": row[3],
        }

    def get_term(self, term: str) -> dict[str, int | str] | None:
        """Retrieve a term's ID and document frequency."""

        row = self.connection.execute(
            """
            SELECT term_id, term, document_frequency
            FROM terms
            WHERE term = ?
            """,
            (term.lower(),),
        ).fetchone()

        if row is None:
            return None

        return {
            "term_id": row[0],
            "term": row[1],
            "document_frequency": row[2],
        }


    def get_postings(self, term: str) -> list[dict[str, str | int]]:
        """Retrieve documents containing a term and their term frequencies."""

        rows = self.connection.execute(
            """
            SELECT p.app_id, d.game_title, p.term_frequency
            FROM terms t
            JOIN postings p ON p.term_id = t.term_id
            JOIN documents d ON d.app_id = p.app_id
            WHERE t.term = ?
            ORDER BY p.term_frequency DESC, p.app_id ASC
            """,
            (term.lower(),),
        ).fetchall()

        return [
            {
                "app_id": row[0],
                "game_title": row[1],
                "term_frequency": row[2],
            }
            for row in rows
        ]


    def get_document_terms(
        self,
        app_id: str,
    ) -> list[dict[str, str | int]]:
        """Retrieve every indexed term and its statistics for a document."""

        rows = self.connection.execute(
            """
            SELECT t.term, p.term_frequency, t.document_frequency
            FROM postings p
            JOIN terms t ON t.term_id = p.term_id
            WHERE p.app_id = ?
            ORDER BY t.term ASC
            """,
            (str(app_id),),
        ).fetchall()

        return [
            {
                "term": row[0],
                "term_frequency": row[1],
                "document_frequency": row[2],
            }
            for row in rows
        ]


    def get_collection_stats(self) -> dict[str, int]:
        """Return basic collection statistics."""

        document_count = self.connection.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

        term_count = self.connection.execute(
            "SELECT COUNT(*) FROM terms"
        ).fetchone()[0]

        posting_count = self.connection.execute(
            "SELECT COUNT(*) FROM postings"
        ).fetchone()[0]

        return {
            "document_count": document_count,
            "term_count": term_count,
            "posting_count": posting_count,
        }

    def integrity_check(self) -> list[str]:
        """Run SQLite and foreign-key integrity checks."""

        problems = []

        result = self.connection.execute(
            "PRAGMA integrity_check"
        ).fetchall()

        for row in result:
            if row[0] != "ok":
                problems.append(row[0])

        foreign_key_errors = self.connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        for error in foreign_key_errors:
            problems.append(f"Foreign-key violation: {error}")

        return problems

    def close(self) -> None:
        """Close the database connection."""

        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()