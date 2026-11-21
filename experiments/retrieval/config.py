
"""Configuration definitions for TF-IDF ranking experiments."""

from dataclasses import dataclass
from enum import Enum
from itertools import product


class TFMethod(str, Enum):
    NATURAL = "natural"
    LOGARITHMIC = "logarithmic"
    MAXIMUM = "maximum"
    BOOLEAN = "boolean"
    LOG_AVERAGE = "log_average"


class IDFMethod(str, Enum):
    CLASSIC = "classic"
    SMOOTHED = "smoothed"
    PROBABILISTIC = "probabilistic"


class NormalizationMethod(str, Enum):
    NONE = "none"
    EUCLIDEAN = "euclidean"


@dataclass(frozen=True)
class ExperimentConfig:
    """Defines the scoring methods and their parameters."""

    tf_method: TFMethod
    idf_method: IDFMethod
    normalization: NormalizationMethod
    alpha: float = 0.5

    def __post_init__(self):
        if not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be between 0 and 1.")

    @property
    def name(self) -> str:
        """Return a readable experiment identifier."""

        return (
            f"tf_{self.tf_method.value}"
            f"__idf_{self.idf_method.value}"
            f"__norm_{self.normalization.value}"
        )


def generate_experiment_configs() -> list[ExperimentConfig]:
    """Generate all combinations of the experimental methods."""

    configurations = []

    for tf_method, idf_method, normalization in product(
        TFMethod,
        IDFMethod,
        NormalizationMethod,
    ):
        configurations.append(
            ExperimentConfig(
                tf_method=tf_method,
                idf_method=idf_method,
                normalization=normalization,
            )
        )

    return configurations
