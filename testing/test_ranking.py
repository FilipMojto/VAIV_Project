
"""Tests for term-frequency calculations."""

import math
import unittest

from experiments.retrieval.config import (
    ExperimentConfig,
    IDFMethod,
    NormalizationMethod,
    TFMethod,
)
from experiments.retrieval.ranking import (
    calculate_idf,
    calculate_tf,
    normalize_document_weights,
    rank_document,
)

class TestTermFrequency(unittest.TestCase):

    def setUp(self):
        self.frequencies = [2, 4, 8]

    def test_natural_tf(self):
        self.assertEqual(
            calculate_tf(4, self.frequencies, TFMethod.NATURAL),
            4.0,
        )

    def test_logarithmic_tf(self):
        self.assertAlmostEqual(
            calculate_tf(4, self.frequencies, TFMethod.LOGARITHMIC),
            1.0 + math.log10(4),
        )

    def test_maximum_tf(self):
        self.assertAlmostEqual(
            calculate_tf(4, self.frequencies, TFMethod.MAXIMUM),
            0.75,
        )

    def test_boolean_tf(self):
        self.assertEqual(
            calculate_tf(4, self.frequencies, TFMethod.BOOLEAN),
            1.0,
        )

    def test_log_average_tf(self):
        expected = (
            1.0 + math.log10(4)
        ) / (
            1.0 + math.log10(14 / 3)
        )

        self.assertAlmostEqual(
            calculate_tf(4, self.frequencies, TFMethod.LOG_AVERAGE),
            expected,
        )

    def test_zero_frequency(self):
        self.assertEqual(
            calculate_tf(0, self.frequencies, TFMethod.NATURAL),
            0.0,
        )

    def test_invalid_negative_frequency(self):
        with self.assertRaises(ValueError):
            calculate_tf(-1, self.frequencies, TFMethod.NATURAL)

    def test_invalid_alpha(self):
        with self.assertRaises(ValueError):
            calculate_tf(4, self.frequencies, TFMethod.MAXIMUM, alpha=1.5)

    def test_empty_document_frequencies(self):
        with self.assertRaises(ValueError):
            calculate_tf(4, [], TFMethod.NATURAL)

    def test_frequency_not_in_document(self):
        with self.assertRaises(ValueError):
            calculate_tf(3, self.frequencies, TFMethod.NATURAL)



class TestInverseDocumentFrequency(unittest.TestCase):

    def test_classic_idf(self):
        result = calculate_idf(10000, 100, IDFMethod.CLASSIC)

        self.assertAlmostEqual(result, 2.0)

    def test_smoothed_idf(self):
        expected = math.log10(10001 / 101) + 1.0

        result = calculate_idf(10000, 100, IDFMethod.SMOOTHED)

        self.assertAlmostEqual(result, expected)

    def test_probabilistic_idf(self):
        expected = math.log10(99)

        result = calculate_idf(10000, 100, IDFMethod.PROBABILISTIC)

        self.assertAlmostEqual(result, expected)

    def test_probabilistic_idf_zero_floor(self):
        result = calculate_idf(10000, 9000, IDFMethod.PROBABILISTIC)

        self.assertEqual(result, 0.0)

    def test_probabilistic_idf_common_term(self):
        result = calculate_idf(10000, 10000, IDFMethod.PROBABILISTIC)

        self.assertEqual(result, 0.0)

    def test_smoothed_idf_for_unseen_term(self):
        result = calculate_idf(10000, 0, IDFMethod.SMOOTHED)

        self.assertAlmostEqual(result, math.log10(10001) + 1.0)

    def test_classic_idf_for_unseen_term(self):
        with self.assertRaises(ValueError):
            calculate_idf(10000, 0, IDFMethod.CLASSIC)

    def test_invalid_document_count(self):
        with self.assertRaises(ValueError):
            calculate_idf(0, 0, IDFMethod.CLASSIC)

    def test_invalid_document_frequency(self):
        with self.assertRaises(ValueError):
            calculate_idf(100, 101, IDFMethod.CLASSIC)



class TestDocumentNormalization(unittest.TestCase):

    def test_no_normalization(self):
        weights = {
            "strategy": 3.0,
            "game": 4.0,
        }

        result = normalize_document_weights(
            weights,
            NormalizationMethod.NONE,
        )

        self.assertEqual(result, weights)

    def test_euclidean_normalization(self):
        weights = {
            "strategy": 3.0,
            "game": 4.0,
        }

        result = normalize_document_weights(
            weights,
            NormalizationMethod.EUCLIDEAN,
        )

        self.assertAlmostEqual(result["strategy"], 0.6)
        self.assertAlmostEqual(result["game"], 0.8)

    def test_all_document_terms_are_normalized(self):
        weights = {
            "strategy": 3.0,
            "game": 4.0,
            "players": 0.0,
        }

        result = normalize_document_weights(
            weights,
            NormalizationMethod.EUCLIDEAN,
        )

        self.assertEqual(set(result), set(weights))
        self.assertAlmostEqual(result["players"], 0.0)

    def test_zero_vector(self):
        weights = {
            "strategy": 0.0,
            "game": 0.0,
        }

        result = normalize_document_weights(
            weights,
            NormalizationMethod.EUCLIDEAN,
        )

        self.assertEqual(result, weights)

    def test_input_is_not_modified(self):
        weights = {
            "strategy": 3.0,
            "game": 4.0,
        }

        original = weights.copy()

        normalize_document_weights(
            weights,
            NormalizationMethod.EUCLIDEAN,
        )

        self.assertEqual(weights, original)



class TestDocumentRanking(unittest.TestCase):

    def test_natural_classic_without_normalization(self):
        config = ExperimentConfig(
            tf_method=TFMethod.NATURAL,
            idf_method=IDFMethod.CLASSIC,
            normalization=NormalizationMethod.NONE,
        )

        document_terms = {
            "strategy": {
                "term_frequency": 3,
                "document_frequency": 2,
            },
            "game": {
                "term_frequency": 1,
                "document_frequency": 3,
            },
        }

        score = rank_document(
            {"strategy": 2},
            document_terms,
            3,
            config,
        )

        expected = 2 * 3 * math.log10(3 / 2)

        self.assertAlmostEqual(score, expected)

    def test_euclidean_normalization_includes_non_query_terms(self):
        config = ExperimentConfig(
            tf_method=TFMethod.NATURAL,
            idf_method=IDFMethod.CLASSIC,
            normalization=NormalizationMethod.EUCLIDEAN,
        )

        document_terms = {
            "strategy": {
                "term_frequency": 3,
                "document_frequency": 2,
            },
            "rare": {
                "term_frequency": 4,
                "document_frequency": 1,
            },
        }

        score = rank_document(
            {"strategy": 1},
            document_terms,
            3,
            config,
        )

        strategy_weight = 3 * math.log10(3 / 2)
        rare_weight = 4 * math.log10(3)

        expected = strategy_weight / math.sqrt(
            strategy_weight ** 2 + rare_weight ** 2
        )

        self.assertAlmostEqual(score, expected)

    def test_empty_document_has_zero_score(self):
        config = ExperimentConfig(
            tf_method=TFMethod.NATURAL,
            idf_method=IDFMethod.CLASSIC,
            normalization=NormalizationMethod.NONE,
        )

        score = rank_document(
            {"strategy": 1},
            {},
            3,
            config,
        )

        self.assertEqual(score, 0.0)


if __name__ == "__main__":
    unittest.main()
