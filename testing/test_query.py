
"""Tests for search query processing."""

import unittest

from src.indexing.query import process_query


class TestQueryProcessing(unittest.TestCase):

    def test_basic_query(self):
        result = process_query(
            "cooperative strategy games for two players"
        )

        self.assertEqual(
            result,
            {
                "cooperative": 1,
                "strategy": 1,
                "games": 1,
                "for": 1,
                "two": 1,
                "players": 1,
            },
        )

    def test_repeated_terms(self):
        result = process_query("strategy strategy games")

        self.assertEqual(
            result,
            {
                "strategy": 2,
                "games": 1,
            },
        )

    def test_case_normalisation(self):
        result = process_query("STRATEGY Strategy strategy")

        self.assertEqual(result, {"strategy": 3})

    def test_punctuation(self):
        result = process_query(
            "strategy, games! (cooperative) players."
        )

        self.assertEqual(
            result,
            {
                "strategy": 1,
                "games": 1,
                "cooperative": 1,
                "players": 1,
            },
        )

    def test_short_tokens_are_excluded(self):
        result = process_query("a an to of it strategy")

        self.assertEqual(result, {"strategy": 1})

    def test_empty_query(self):
        self.assertEqual(process_query(""), {})

    def test_whitespace_only_query(self):
        self.assertEqual(process_query("   \t\n  "), {})


if __name__ == "__main__":
    unittest.main()
