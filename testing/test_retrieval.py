
"""Tests for candidate document retrieval."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from experiments.retrieval.config import (
    ExperimentConfig,
    IDFMethod,
    NormalizationMethod,
    TFMethod,
)
from experiments.retrieval.ranking import (
    rank_candidates,
    rank_configurations,
    rank_configurations_with_metrics,
)
from src.indexing.database import SCHEMA, SCHEMA_VERSION, SQLiteIndex
from src.indexing.retrieval import iter_candidates_with_document_terms, retrieve_candidates

class TestCandidateRetrieval(unittest.TestCase):

    def setUp(self):
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
        self.index.close()
        self.temp_dir.cleanup()

    def test_single_term_retrieval(self):
        results = retrieve_candidates(
            self.index,
            {"strategy": 1},
        )

        self.assertEqual(set(results), {"1", "2"})

    def test_multiple_term_retrieval(self):
        results = retrieve_candidates(
            self.index,
            {"strategy": 1, "game": 1},
        )

        self.assertEqual(set(results), {"1", "2", "3"})

        self.assertEqual(
            set(results["1"]["matched_terms"]),
            {"strategy", "game"},
        )

    def test_query_frequency_is_preserved(self):
        results = retrieve_candidates(
            self.index,
            {"strategy": 3},
        )

        self.assertEqual(
            results["1"]["matched_terms"]["strategy"]["query_frequency"],
            3,
        )

    def test_term_frequencies_are_preserved(self):
        results = retrieve_candidates(
            self.index,
            {"strategy": 1},
        )

        self.assertEqual(
            results["1"]["matched_terms"]["strategy"]["term_frequency"],
            3,
        )

    def test_missing_terms_are_ignored(self):
        results = retrieve_candidates(
            self.index,
            {"nonexistent": 1},
        )

        self.assertEqual(results, {})

    def test_mixed_existing_and_missing_terms(self):
        results = retrieve_candidates(
            self.index,
            {"strategy": 1, "nonexistent": 1},
        )

        self.assertEqual(set(results), {"1", "2"})

    def test_empty_query(self):
        self.assertEqual(
            retrieve_candidates(self.index, {}),
            {},
        )


    def test_complete_document_terms_are_retrieved(self):
        candidates = retrieve_candidates(
            self.index,
            {"strategy": 1},
        )

        enriched = dict(
            iter_candidates_with_document_terms(
                self.index,
                candidates,
            )
        )

        document = enriched["1"]

        self.assertEqual(
            set(document["document_terms"]),
            {"strategy", "game"},
        )

        self.assertEqual(
            document["document_terms"]["game"]["term_frequency"],
            1,
        )

    def test_document_terms_include_non_query_terms(self):
        candidates = retrieve_candidates(
            self.index,
            {"strategy": 1},
        )

        enriched = dict(
            iter_candidates_with_document_terms(
                self.index,
                candidates,
            )
        )

        self.assertNotIn(
            "game",
            enriched["1"]["matched_terms"],
        )

        self.assertIn(
            "game",
            enriched["1"]["document_terms"],
        )


    def test_candidates_are_ranked_by_score(self):
        candidates = retrieve_candidates(
            self.index,
            {"strategy": 1},
        )

        config = ExperimentConfig(
            tf_method=TFMethod.NATURAL,
            idf_method=IDFMethod.CLASSIC,
            normalization=NormalizationMethod.NONE,
        )

        results = rank_candidates(
            self.index,
            candidates,
            {"strategy": 1},
            config,
        )

        self.assertEqual(
            [result.app_id for result in results],
            ["1", "2"],
        )

        self.assertGreater(results[0].score, results[1].score)

        self.assertEqual(
            [result.rank for result in results],
            [1, 2],
        )

    def test_equal_scores_have_deterministic_order(self):
        candidates = retrieve_candidates(
            self.index,
            {"strategy": 1},
        )

        config = ExperimentConfig(
            tf_method=TFMethod.BOOLEAN,
            idf_method=IDFMethod.CLASSIC,
            normalization=NormalizationMethod.NONE,
        )

        results = rank_candidates(
            self.index,
            candidates,
            {"strategy": 1},
            config,
        )

        self.assertEqual(
            [result.app_id for result in results],
            ["1", "2"],
        )

        self.assertAlmostEqual(
            results[0].score,
            results[1].score,
        )

    def test_empty_candidates_return_empty_results(self):
        config = ExperimentConfig(
            tf_method=TFMethod.NATURAL,
            idf_method=IDFMethod.CLASSIC,
            normalization=NormalizationMethod.NONE,
        )

        results = rank_candidates(
            self.index,
            {},
            {"strategy": 1},
            config,
        )

        self.assertEqual(results, [])



    def test_multiple_configurations_are_ranked(self):
        candidates = retrieve_candidates(
            self.index,
            {"strategy": 1},
        )

        configurations = [
            ExperimentConfig(
                tf_method=TFMethod.NATURAL,
                idf_method=IDFMethod.CLASSIC,
                normalization=NormalizationMethod.NONE,
            ),
            ExperimentConfig(
                tf_method=TFMethod.BOOLEAN,
                idf_method=IDFMethod.CLASSIC,
                normalization=NormalizationMethod.NONE,
            ),
        ]

        results = rank_configurations(
            self.index,
            candidates,
            {"strategy": 1},
            configurations,
        )

        self.assertEqual(
            set(results),
            {config.name for config in configurations},
        )

        for config in configurations:
            self.assertEqual(len(results[config.name]), 2)

    def test_multiple_configuration_results_match_individual_ranking(self):
        candidates = retrieve_candidates(
            self.index,
            {"strategy": 1},
        )

        config = ExperimentConfig(
            tf_method=TFMethod.NATURAL,
            idf_method=IDFMethod.CLASSIC,
            normalization=NormalizationMethod.NONE,
        )

        multiple_results = rank_configurations(
            self.index,
            candidates,
            {"strategy": 1},
            [config],
        )[config.name]

        individual_results = rank_candidates(
            self.index,
            candidates,
            {"strategy": 1},
            config,
        )

        self.assertEqual(multiple_results, individual_results)

    def test_duplicate_configuration_names_are_rejected(self):
        config = ExperimentConfig(
            tf_method=TFMethod.NATURAL,
            idf_method=IDFMethod.CLASSIC,
            normalization=NormalizationMethod.NONE,
        )

        with self.assertRaises(ValueError):
            rank_configurations(
                self.index,
                {},
                {"strategy": 1},
                [config, config],
            )

    def test_timed_ranking_matches_untimed_ranking(self):
        candidates = retrieve_candidates(
            self.index,
            {"strategy": 1},
        )

        configurations = [
            ExperimentConfig(
                tf_method=TFMethod.NATURAL,
                idf_method=IDFMethod.CLASSIC,
                normalization=NormalizationMethod.NONE,
            ),
            ExperimentConfig(
                tf_method=TFMethod.BOOLEAN,
                idf_method=IDFMethod.CLASSIC,
                normalization=NormalizationMethod.EUCLIDEAN,
            ),
        ]

        timed_results, metrics = rank_configurations_with_metrics(
            self.index,
            candidates,
            {"strategy": 1},
            configurations,
        )

        untimed_results = rank_configurations(
            self.index,
            candidates,
            {"strategy": 1},
            configurations,
        )

        self.assertEqual(timed_results, untimed_results)
        self.assertGreaterEqual(metrics["document_enrichment_seconds"], 0)
        self.assertGreaterEqual(metrics["ranking_wall_seconds"], 0)

        for config in configurations:
            config_metrics = metrics["configurations"][config.name]

            self.assertEqual(
                config_metrics["documents_ranked"],
                len(candidates),
            )
            self.assertGreaterEqual(config_metrics["scoring_seconds"], 0)
            self.assertGreaterEqual(config_metrics["sorting_seconds"], 0)
            self.assertGreaterEqual(config_metrics["total_seconds"], 0)



if __name__ == "__main__":
    unittest.main()
