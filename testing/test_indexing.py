
"""Tests for persistent SQLite index access."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.indexing.database import SCHEMA, SCHEMA_VERSION, SQLiteIndex


class TestSQLiteIndexReader(unittest.TestCase):

    def setUp(self):
        """Create a small temporary index for each test."""

        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test_index.sqlite3"

        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)

        connection.executemany(
            """
            INSERT INTO documents (app_id, game_title, designer, publisher)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("1", "Strategy Game", "Designer A", "Publisher A"),
                ("2", "Another Strategy Game", "Designer B", "Publisher B"),
                ("3", "Board Game", "Designer C", "Publisher C"),
            ],
        )

        connection.executemany(
            """
            INSERT INTO terms (term_id, term, document_frequency)
            VALUES (?, ?, ?)
            """,
            [
                (1, "strategy", 2),
                (2, "game", 3),
            ],
        )

        connection.executemany(
            """
            INSERT INTO postings (app_id, term_id, term_frequency)
            VALUES (?, ?, ?)
            """,
            [
                ("1", 1, 3),
                ("2", 1, 1),
                ("1", 2, 1),
                ("2", 2, 2),
                ("3", 2, 4),
            ],
        )

        connection.execute(
            """
            INSERT INTO index_metadata (key, value)
            VALUES ('schema_version', ?)
            """,
            (SCHEMA_VERSION,),
        )

        connection.commit()
        connection.close()

        self.index = SQLiteIndex(self.database_path)

    def tearDown(self):
        """Close the index and remove the temporary database."""

        self.index.close()
        self.temp_dir.cleanup()

    def test_get_document(self):
        document = self.index.get_document("1")

        self.assertEqual(
            document,
            {
                "app_id": "1",
                "game_title": "Strategy Game",
                "designer": "Designer A",
                "publisher": "Publisher A",
            },
        )

    def test_get_missing_document(self):
        self.assertIsNone(self.index.get_document("999"))

    def test_get_term(self):
        term = self.index.get_term("strategy")

        self.assertEqual(
            term,
            {
                "term_id": 1,
                "term": "strategy",
                "document_frequency": 2,
            },
        )

    def test_term_case_normalisation(self):
        self.assertEqual(
            self.index.get_term("STRATEGY"),
            self.index.get_term("strategy"),
        )

    def test_get_missing_term(self):
        self.assertIsNone(self.index.get_term("nonexistent"))

    def test_get_postings(self):
        postings = self.index.get_postings("strategy")

        self.assertEqual(
            postings,
            [
                {
                    "app_id": "1",
                    "game_title": "Strategy Game",
                    "term_frequency": 3,
                },
                {
                    "app_id": "2",
                    "game_title": "Another Strategy Game",
                    "term_frequency": 1,
                },
            ],
        )

    def test_postings_match_document_frequency(self):
        term = self.index.get_term("strategy")
        postings = self.index.get_postings("strategy")

        self.assertEqual(
            len(postings),
            term["document_frequency"],
        )

    def test_get_postings_for_missing_term(self):
        self.assertEqual(
            self.index.get_postings("nonexistent"),
            [],
        )

    def test_get_document_terms(self):
        terms = self.index.get_document_terms("1")

        self.assertEqual(
            terms,
            [
                {
                    "term": "game",
                    "term_frequency": 1,
                    "document_frequency": 3,
                },
                {
                    "term": "strategy",
                    "term_frequency": 3,
                    "document_frequency": 2,
                },
            ],
        )

    def test_get_document_terms_for_missing_document(self):
        self.assertEqual(
            self.index.get_document_terms("999"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
