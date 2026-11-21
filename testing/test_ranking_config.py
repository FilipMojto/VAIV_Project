
"""Tests for ranking experiment configurations."""

import unittest

from experiments.retrieval.config import (
    ExperimentConfig,
    TFMethod,
    IDFMethod,
    NormalizationMethod,
    generate_experiment_configs,
)


class TestExperimentConfig(unittest.TestCase):

    def test_generate_all_configurations(self):
        configurations = generate_experiment_configs()

        self.assertEqual(len(configurations), 30)

    def test_configurations_are_unique(self):
        configurations = generate_experiment_configs()
        names = [config.name for config in configurations]

        self.assertEqual(len(names), len(set(names)))

    def test_all_methods_are_represented(self):
        configurations = generate_experiment_configs()

        self.assertEqual(
            {config.tf_method for config in configurations},
            set(TFMethod),
        )

        self.assertEqual(
            {config.idf_method for config in configurations},
            set(IDFMethod),
        )

        self.assertEqual(
            {config.normalization for config in configurations},
            set(NormalizationMethod),
        )

    def test_default_alpha(self):
        config = ExperimentConfig(
            TFMethod.MAXIMUM,
            IDFMethod.CLASSIC,
            NormalizationMethod.NONE,
        )

        self.assertEqual(config.alpha, 0.5)

    def test_custom_alpha(self):
        config = ExperimentConfig(
            TFMethod.MAXIMUM,
            IDFMethod.CLASSIC,
            NormalizationMethod.NONE,
            alpha=0.25,
        )

        self.assertEqual(config.alpha, 0.25)

    def test_invalid_alpha(self):
        with self.assertRaises(ValueError):
            ExperimentConfig(
                TFMethod.MAXIMUM,
                IDFMethod.CLASSIC,
                NormalizationMethod.NONE,
                alpha=1.5,
            )

    def test_configuration_name(self):
        config = ExperimentConfig(
            TFMethod.LOGARITHMIC,
            IDFMethod.SMOOTHED,
            NormalizationMethod.EUCLIDEAN,
        )

        self.assertEqual(
            config.name,
            "tf_logarithmic__idf_smoothed__norm_euclidean",
        )


if __name__ == "__main__":
    unittest.main()
