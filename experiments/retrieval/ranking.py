
"""Term-frequency calculations for retrieval experiments."""

import math
from time import perf_counter

from experiments.retrieval.config import (
    ExperimentConfig,
    IDFMethod,
    TFMethod,
    NormalizationMethod,
)

from src.indexing.retrieval import iter_candidates_with_document_terms
from experiments.retrieval.results import SearchResult

def calculate_tf(
    term_frequency: int,
    document_term_frequencies: list[int],
    method: TFMethod,
    alpha: float = 0.5,
) -> float:
    """Calculate a term's TF weight using the selected method."""

    if term_frequency < 0:
        raise ValueError("Term frequency cannot be negative.")

    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be between 0 and 1.")

    if term_frequency == 0:
        return 0.0

    if not document_term_frequencies:
        raise ValueError("Document term frequencies cannot be empty.")

    if any(tf <= 0 for tf in document_term_frequencies):
        raise ValueError(
            "Document term frequencies must contain only positive values."
        )

    if term_frequency not in document_term_frequencies:
        raise ValueError(
            "Term frequency must occur in the document term frequencies."
        )

    if method == TFMethod.NATURAL:
        return float(term_frequency)

    if method == TFMethod.LOGARITHMIC:
        return 1.0 + math.log10(term_frequency)

    if method == TFMethod.MAXIMUM:
        maximum_frequency = max(document_term_frequencies)

        return (
            alpha
            + (1.0 - alpha) * term_frequency / maximum_frequency
        )

    if method == TFMethod.BOOLEAN:
        return 1.0

    if method == TFMethod.LOG_AVERAGE:
        average_frequency = (
            sum(document_term_frequencies)
            / len(document_term_frequencies)
        )

        return (
            (1.0 + math.log10(term_frequency))
            / (1.0 + math.log10(average_frequency))
        )

    raise ValueError(f"Unsupported TF method: {method}")



def calculate_idf(
    document_count: int,
    document_frequency: int,
    method: IDFMethod,
) -> float:
    """Calculate inverse document frequency using the selected method."""

    if document_count <= 0:
        raise ValueError("Document count must be positive.")

    if not 0 <= document_frequency <= document_count:
        raise ValueError(
            "Document frequency must be between zero and document count."
        )

    if method == IDFMethod.CLASSIC:
        if document_frequency == 0:
            raise ValueError(
                "Classic IDF is undefined for terms absent from the collection."
            )

        return math.log10(document_count / document_frequency)

    if method == IDFMethod.SMOOTHED:
        return math.log10(
            (document_count + 1) / (document_frequency + 1)
        ) + 1.0

    if method == IDFMethod.PROBABILISTIC:
        if document_frequency == 0:
            raise ValueError(
                "Probabilistic IDF is undefined for terms absent from the collection."
            )

        if document_frequency == document_count:
            return 0.0

        return max(
            0.0,
            math.log10(
                (document_count - document_frequency)
                / document_frequency
            ),
        )

    raise ValueError(f"Unsupported IDF method: {method}")


def normalize_document_weights(
    term_weights: dict[str, float],
    method: NormalizationMethod,
) -> dict[str, float]:
    """Normalize all term weights in a document."""

    if method == NormalizationMethod.NONE:
        return dict(term_weights)

    if method == NormalizationMethod.EUCLIDEAN:
        norm = math.sqrt(
            sum(weight ** 2 for weight in term_weights.values())
        )

        if norm == 0.0:
            return {
                term: 0.0
                for term in term_weights
            }

        return {
            term: weight / norm
            for term, weight in term_weights.items()
        }

    raise ValueError(f"Unsupported normalization method: {method}")


def rank_document(
    query_terms: dict[str, int],
    document_terms: dict[str, dict[str, int]],
    document_count: int,
    config: ExperimentConfig,
) -> float:
    """Calculate the ranking score of one document for a query."""

    if document_count <= 0:
        raise ValueError("Document count must be positive.")

    if not document_terms:
        return 0.0

    document_term_frequencies = [
        item["term_frequency"]
        for item in document_terms.values()
    ]

    # Calculate TF-IDF weights for every term in the document.
    term_weights = {}

    for term, statistics in document_terms.items():
        tf_weight = calculate_tf(
            statistics["term_frequency"],
            document_term_frequencies,
            config.tf_method,
            config.alpha,
        )

        idf_weight = calculate_idf(
            document_count,
            statistics["document_frequency"],
            config.idf_method,
        )

        term_weights[term] = tf_weight * idf_weight

    # Normalise the complete document vector, not just query terms.
    normalized_weights = normalize_document_weights(
        term_weights,
        config.normalization,
    )

    # Query TF remains natural frequency; IDF is applied only once.
    score = sum(
        query_frequency * normalized_weights.get(term, 0.0)
        for term, query_frequency in query_terms.items()
    )

    return score




def rank_configurations_with_metrics(
    index,
    candidates: dict[str, dict],
    query_terms: dict[str, int],
    configurations: list[ExperimentConfig],
) -> tuple[dict[str, list[SearchResult]], dict]:
    """Rank candidates under multiple configurations and measure each stage."""

    names = [config.name for config in configurations]

    if len(names) != len(set(names)):
        raise ValueError("Experiment configuration names must be unique.")

    results_by_config = {
        config.name: []
        for config in configurations
    }

    metrics = {
        "document_enrichment_seconds": 0.0,
        "ranking_wall_seconds": 0.0,
        "configurations": {
            config.name: {
                "scoring_seconds": 0.0,
                "sorting_seconds": 0.0,
                "total_seconds": 0.0,
                "documents_ranked": 0,
            }
            for config in configurations
        },
    }

    if not candidates or not query_terms or not configurations:
        return results_by_config, metrics

    ranking_start = perf_counter()
    document_count = index.get_collection_stats()["document_count"]

    iterator = iter_candidates_with_document_terms(index, candidates)

    while True:
        enrichment_start = perf_counter()

        try:
            app_id, candidate = next(iterator)
        except StopIteration:
            break

        metrics["document_enrichment_seconds"] += (
            perf_counter() - enrichment_start
        )

        document_terms = candidate["document_terms"]

        for config in configurations:
            config_metrics = metrics["configurations"][config.name]

            scoring_start = perf_counter()

            score = rank_document(
                query_terms,
                document_terms,
                document_count,
                config,
            )

            config_metrics["scoring_seconds"] += (
                perf_counter() - scoring_start
            )
            config_metrics["documents_ranked"] += 1

            results_by_config[config.name].append(
                {
                    "app_id": app_id,
                    "game_title": candidate["document"]["game_title"],
                    "score": score,
                }
            )

    ranked_results = {}

    for config_name, scored_results in results_by_config.items():
        config_metrics = metrics["configurations"][config_name]
        sorting_start = perf_counter()

        scored_results.sort(
            key=lambda result: (
                -result["score"],
                result["app_id"],
            )
        )

        ranked_results[config_name] = [
            SearchResult(
                app_id=result["app_id"],
                game_title=result["game_title"],
                score=result["score"],
                rank=position,
            )
            for position, result in enumerate(
                scored_results,
                start=1,
            )
        ]

        config_metrics["sorting_seconds"] = (
            perf_counter() - sorting_start
        )
        config_metrics["total_seconds"] = (
            config_metrics["scoring_seconds"]
            + config_metrics["sorting_seconds"]
        )

    metrics["ranking_wall_seconds"] = perf_counter() - ranking_start

    return ranked_results, metrics


def rank_configurations(
    index,
    candidates: dict[str, dict],
    query_terms: dict[str, int],
    configurations: list[ExperimentConfig],
) -> dict[str, list[SearchResult]]:
    """Rank candidates under multiple configurations."""

    results, _ = rank_configurations_with_metrics(
        index,
        candidates,
        query_terms,
        configurations,
    )

    return results


def rank_candidates(
    index,
    candidates: dict[str, dict],
    query_terms: dict[str, int],
    config: ExperimentConfig,
) -> list[SearchResult]:
    """Rank candidates using one experiment configuration."""

    return rank_configurations(
        index,
        candidates,
        query_terms,
        [config],
    )[config.name]