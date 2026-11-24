"""Search the existing SQLite BGG index using one TF-IDF configuration."""

import argparse
from pathlib import Path

from experiments.retrieval.config import (
    ExperimentConfig,
    IDFMethod,
    NormalizationMethod,
    TFMethod,
)
from experiments.retrieval.ranking import rank_candidates
from src.indexing.database import SQLiteIndex
from src.indexing.query import process_query
from src.indexing.retrieval import retrieve_candidates


DEFAULT_DATABASE = Path("data/indexes/bgg_games.sqlite3")


def search(
    database_path: Path,
    query: str,
    top_k: int = 10,
    config: ExperimentConfig | None = None,
):
    """Search the existing index and return ranked results."""

    if top_k <= 0:
        raise ValueError("top_k must be positive.")

    if config is None:
        config = ExperimentConfig(
            tf_method=TFMethod.LOGARITHMIC,
            idf_method=IDFMethod.SMOOTHED,
            normalization=NormalizationMethod.EUCLIDEAN,
        )

    query_terms = process_query(query)

    if not query_terms:
        return query_terms, {}, []

    with SQLiteIndex(database_path) as index:
        candidates = retrieve_candidates(index, query_terms)
        results = rank_candidates(
            index,
            candidates,
            query_terms,
            config,
        )

    return query_terms, candidates, results[:top_k]


def main():
    parser = argparse.ArgumentParser(
        description="Search the existing SQLite BGG index."
    )

    parser.add_argument(
        "query",
        help="Search query.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help=f"SQLite index path (default: {DEFAULT_DATABASE}).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of results to display (default: 10).",
    )
    parser.add_argument(
        "--tf",
        choices=[method.value for method in TFMethod],
        default=TFMethod.LOGARITHMIC.value,
        help="Term-frequency method.",
    )
    parser.add_argument(
        "--idf",
        choices=[method.value for method in IDFMethod],
        default=IDFMethod.SMOOTHED.value,
        help="Inverse document-frequency method.",
    )
    parser.add_argument(
        "--normalization",
        choices=[method.value for method in NormalizationMethod],
        default=NormalizationMethod.EUCLIDEAN.value,
        help="Document-vector normalization.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.5,
        help="Alpha parameter for maximum TF (default: 0.5).",
    )

    args = parser.parse_args()

    if args.top <= 0:
        parser.error("--top must be positive.")

    try:
        config = ExperimentConfig(
            tf_method=TFMethod(args.tf),
            idf_method=IDFMethod(args.idf),
            normalization=NormalizationMethod(args.normalization),
            alpha=args.alpha,
        )

        query_terms, candidates, results = search(
            database_path=args.database,
            query=args.query,
            top_k=args.top,
            config=config,
        )

    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    print("\n=== SQLITE BGG SEARCH ===")
    print(f"Database: {args.database}")
    print(f"Query: {args.query}")
    print(f"Processed terms: {query_terms}")
    print(f"TF-IDF configuration: {config.name}")
    print(f"Candidates retrieved: {len(candidates)}")

    if not query_terms:
        print("\nNo searchable terms found.")
        return

    if not results:
        print("\nNo matching games found.")
        return

    print(f"\n=== TOP {len(results)} RESULTS ===")
    for result in results:
        print(
            f"{result.rank:>2}. {result.game_title} "
            f"(BGG ID: {result.app_id}, score: {result.score:.6f})"
        )


if __name__ == "__main__":
    main()
