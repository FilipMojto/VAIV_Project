"""Tests for the SQLite and Lucene search entry points."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from experiments.retrieval.config import (
    ExperimentConfig,
    IDFMethod,
    NormalizationMethod,
    TFMethod,
)
from experiments.retrieval import search_sqlite, search_lucene
from experiments.retrieval.search_lucene import format_wiki_value


class TestSQLiteSearchCLI(unittest.TestCase):

    @patch("experiments.retrieval.search_sqlite.rank_candidates")
    @patch("experiments.retrieval.search_sqlite.retrieve_candidates")
    @patch("experiments.retrieval.search_sqlite.process_query")
    @patch("experiments.retrieval.search_sqlite.SQLiteIndex")
    def test_search_uses_default_configuration(
        self,
        mock_index_class,
        mock_process_query,
        mock_retrieve_candidates,
        mock_rank_candidates,
    ):
        mock_index = mock_index_class.return_value.__enter__.return_value
        mock_process_query.return_value = {"cooperative": 1}
        mock_retrieve_candidates.return_value = {"1", "2"}
        mock_rank_candidates.return_value = [
            MagicMock(app_id=str(i), rank=i) for i in range(1, 4)
        ]

        query_terms, candidates, results = search_sqlite.search(
            Path("test.sqlite3"),
            "cooperative",
            top_k=2,
        )

        self.assertEqual(query_terms, {"cooperative": 1})
        self.assertEqual(candidates, {"1", "2"})
        self.assertEqual(len(results), 2)

        config = mock_rank_candidates.call_args.args[3]
        self.assertEqual(config.tf_method, TFMethod.LOGARITHMIC)
        self.assertEqual(config.idf_method, IDFMethod.SMOOTHED)
        self.assertEqual(
            config.normalization,
            NormalizationMethod.EUCLIDEAN,
        )

        mock_index_class.assert_called_once_with(Path("test.sqlite3"))
        mock_process_query.assert_called_once_with("cooperative")
        mock_retrieve_candidates.assert_called_once_with(
            mock_index,
            query_terms,
        )

    @patch("experiments.retrieval.search_sqlite.rank_candidates")
    @patch("experiments.retrieval.search_sqlite.retrieve_candidates")
    @patch("experiments.retrieval.search_sqlite.process_query")
    @patch("experiments.retrieval.search_sqlite.SQLiteIndex")
    def test_search_uses_custom_configuration(
        self,
        mock_index_class,
        mock_process_query,
        mock_retrieve_candidates,
        mock_rank_candidates,
    ):
        mock_process_query.return_value = {"strategy": 1}
        mock_retrieve_candidates.return_value = {"1"}
        mock_rank_candidates.return_value = []

        config = ExperimentConfig(
            TFMethod.MAXIMUM,
            IDFMethod.PROBABILISTIC,
            NormalizationMethod.NONE,
            alpha=0.25,
        )

        search_sqlite.search(
            Path("test.sqlite3"),
            "strategy",
            config=config,
        )

        self.assertIs(
            mock_rank_candidates.call_args.args[3],
            config,
        )

    @patch("experiments.retrieval.search_sqlite.SQLiteIndex")
    @patch("experiments.retrieval.search_sqlite.process_query")
    def test_search_skips_index_for_unsearchable_query(
        self,
        mock_process_query,
        mock_index_class,
    ):
        mock_process_query.return_value = {}

        query_terms, candidates, results = search_sqlite.search(
            Path("test.sqlite3"),
            "!? ",
        )

        self.assertEqual(query_terms, {})
        self.assertEqual(candidates, {})
        self.assertEqual(results, [])
        mock_index_class.assert_not_called()

    def test_search_rejects_nonpositive_top_k(self):
        with self.assertRaises(ValueError):
            search_sqlite.search(
                Path("test.sqlite3"),
                "strategy",
                top_k=0,
            )


class TestLuceneSearchCLI(unittest.TestCase):

    def setUp(self):
        self.searcher_patcher = patch(
            "experiments.retrieval.search_lucene.LuceneSearcher"
        )
        self.mock_searcher_class = self.searcher_patcher.start()
        self.addCleanup(self.searcher_patcher.stop)

        self.searcher = (
            self.mock_searcher_class.return_value.__enter__.return_value
        )

    def test_text_search_uses_default_field_and_or(self):
        expected = {"total_hits": 2, "results": []}
        self.searcher.search_text.return_value = expected

        result = search_lucene.search(
            Path("lucene_bgg"),
            mode="text",
            query="settlers catan",
        )

        self.assertIs(result, expected)
        self.searcher.search_text.assert_called_once_with(
            "settlers catan",
            field="bgg_all_text",
            operator="OR",
            limit=10,
        )

    def test_text_search_passes_custom_arguments(self):
        self.searcher.search_text.return_value = {
            "total_hits": 0,
            "results": [],
        }

        search_lucene.search(
            Path("lucene_bgg"),
            mode="text",
            query="settlers catan",
            field="game_title",
            operator="AND",
            limit=5,
        )

        self.searcher.search_text.assert_called_once_with(
            "settlers catan",
            field="game_title",
            operator="AND",
            limit=5,
        )

    def test_phrase_search_uses_title_field(self):
        self.searcher.search_phrase.return_value = {
            "total_hits": 1,
            "results": [],
        }

        search_lucene.search(
            Path("lucene_bgg"),
            mode="phrase",
            query="settlers of catan",
        )

        self.searcher.search_phrase.assert_called_once_with(
            "settlers of catan",
            field="game_title",
            limit=10,
        )

    def test_fuzzy_search_passes_edit_distance(self):
        self.searcher.search_fuzzy.return_value = {
            "total_hits": 1,
            "results": [],
        }

        search_lucene.search(
            Path("lucene_bgg"),
            mode="fuzzy",
            query="catna",
            max_edits=1,
            limit=5,
        )

        self.searcher.search_fuzzy.assert_called_once_with(
            "catna",
            field="game_title",
            max_edits=1,
            limit=5,
        )

    def test_range_search_uses_release_year_field(self):
        self.searcher.search_range.return_value = {
            "total_hits": 10,
            "results": [],
        }

        search_lucene.search(
            Path("lucene_bgg"),
            mode="range",
            lower=1990,
            upper=2000,
        )

        self.searcher.search_range.assert_called_once_with(
            field="release_year",
            lower=1990,
            upper=2000,
            limit=10,
        )

    def test_range_search_requires_both_bounds(self):
        with self.assertRaisesRegex(ValueError, "Both --lower and --upper"):
            search_lucene.search(
                Path("lucene_bgg"),
                mode="range",
                lower=1990,
            )

        self.searcher.search_range.assert_not_called()

    def test_search_rejects_missing_text_query(self):
        with self.assertRaisesRegex(ValueError, "query is required"):
            search_lucene.search(
                Path("lucene_bgg"),
                mode="text",
            )

        self.searcher.search_text.assert_not_called()

    def test_search_rejects_nonpositive_limit(self):
        with self.assertRaises(ValueError):
            search_lucene.search(
                Path("lucene_bgg"),
                mode="text",
                query="catan",
                limit=0,
            )

        self.mock_searcher_class.assert_not_called()

    def test_search_rejects_unsupported_mode(self):
        with self.assertRaisesRegex(ValueError, "Unsupported search mode"):
            search_lucene.search(
                Path("lucene_bgg"),
                mode="unsupported",
                query="catan",
            )


class TestWikipediaOutputFormatting(unittest.TestCase):

    def test_formats_publisher_list(self):
        value = (
            "* Kosmos (Germany)\n"
            "* Catan Studio (English-language)\n"
            "* Filosofia (France)"
        )

        self.assertEqual(
            format_wiki_value("wiki_publisher", value),
            [
                "Kosmos (Germany)",
                "Catan Studio (English-language)",
                "Filosofia (France)",
            ],
        )

    def test_formats_player_configurations(self):
        value = "3–4 (standard)|5–6 (with extensions)"

        self.assertEqual(
            format_wiki_value("wiki_number_of_players", value),
            [
                "3–4 (standard)",
                "5–6 (with extensions)",
            ],
        )

    def test_preserves_other_wikipedia_values(self):
        self.assertEqual(
            format_wiki_value("wiki_designer", "Klaus Teuber"),
            ["Klaus Teuber"],
        )

    def test_formats_missing_values(self):
        self.assertEqual(
            format_wiki_value("wiki_publisher", None),
            ["—"],
        )

    def test_formats_inline_publisher_list(self):
        value = (
            "* Kosmos (Germany) * "
            "Catan Studio (English-language) * "
            "Filosofia (France)"
        )

        self.assertEqual(
            format_wiki_value("wiki_publisher", value),
            [
                "Kosmos (Germany)",
                "Catan Studio (English-language)",
                "Filosofia (France)",
            ],
        )


if __name__ == "__main__":
    unittest.main()
