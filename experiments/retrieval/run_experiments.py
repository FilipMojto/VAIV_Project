
"""Run and record all TF-IDF ranking configurations on the BGG index."""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from time import perf_counter

from experiments.retrieval.config import generate_experiment_configs
from experiments.retrieval.ranking import rank_configurations_with_metrics
from src.indexing.database import SQLiteIndex
from src.indexing.query import process_query
from src.indexing.retrieval import retrieve_candidates


DEFAULT_DATABASE = Path("data/indexes/bgg_games.sqlite3")
DEFAULT_OUTPUT_DIR = Path("data/experiment_results")


def save_report(report: dict, query: str, output_dir: Path) -> Path:
    """Save an experiment report as a timestamped JSON file."""

    output_dir.mkdir(parents=True, exist_ok=True)

    query_slug = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")

    output_path = output_dir / f"{query_slug}_{timestamp}.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output_path


def run_experiment(
    database_path: Path,
    query: str,
    top_k: int = 10,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path | None:
    """Execute and record all ranking configurations for one query."""

    overall_start = perf_counter()

    query_start = perf_counter()
    query_terms = process_query(query)
    query_processing_time = perf_counter() - query_start

    print(f"\nQuery: {query}")
    print(f"Processed terms: {query_terms}")

    if not query_terms:
        print("No searchable terms found.")
        return None

    with SQLiteIndex(database_path) as index:
        metadata = index.get_metadata()

        retrieval_start = perf_counter()
        candidates = retrieve_candidates(index, query_terms)
        retrieval_time = perf_counter() - retrieval_start

        configurations = generate_experiment_configs()

        results, ranking_metrics = rank_configurations_with_metrics(
            index,
            candidates,
            query_terms,
            configurations,
        )

        total_time = perf_counter() - overall_start

        configuration_details = {}

        for config in configurations:
            config_results = results[config.name]
            config_metrics = ranking_metrics["configurations"][config.name]

            configuration_details[config.name] = {
                "tf_method": config.tf_method.value,
                "idf_method": config.idf_method.value,
                "normalization": config.normalization.value,
                "alpha": config.alpha,
                "timing": config_metrics,
                "top_results": [
                    {
                        "rank": result.rank,
                        "app_id": result.app_id,
                        "game_title": result.game_title,
                        "score": result.score,
                    }
                    for result in config_results[:top_k]
                ],
            }

        report = {
            "created_at": datetime.now().astimezone().isoformat(),
            "query": query,
            "processed_terms": query_terms,
            "dataset": {
                "source_filename": metadata.get("source_filename"),
                "source_sha256": metadata.get("source_sha256"),
                "document_count": metadata.get("document_count"),
            },
            "index": {
                "database_path": str(database_path),
                "schema_version": metadata.get("schema_version"),
                "tokenizer_pattern": metadata.get("tokenizer_pattern"),
                "indexed_fields": json.loads(
                    metadata.get("indexed_fields", "[]")
                ),
            },
            "experiment": {
                "configuration_count": len(configurations),
                "candidate_count": len(candidates),
                "top_k": top_k,
            },
            "timings": {
                "query_processing_seconds": query_processing_time,
                "candidate_retrieval_seconds": retrieval_time,
                "document_enrichment_seconds": (
                    ranking_metrics["document_enrichment_seconds"]
                ),
                "ranking_wall_seconds": (
                    ranking_metrics["ranking_wall_seconds"]
                ),
                "total_experiment_seconds": total_time,
            },
            "configurations": configuration_details,
        }

    report_path = save_report(report, query, output_dir)

    print("\n=== EXPERIMENT SUMMARY ===")
    print(f"Candidates retrieved: {len(candidates)}")
    print(f"Configurations: {len(configurations)}")
    print(f"Query processing: {query_processing_time:.4f} seconds")
    print(f"Candidate retrieval: {retrieval_time:.4f} seconds")
    print(
        "Document enrichment: "
        f"{ranking_metrics['document_enrichment_seconds']:.4f} seconds"
    )
    print(
        "Complete ranking stage: "
        f"{ranking_metrics['ranking_wall_seconds']:.4f} seconds"
    )
    print(f"Total experiment: {total_time:.4f} seconds")

    fastest = sorted(
        ranking_metrics["configurations"].items(),
        key=lambda item: item[1]["total_seconds"],
    )

    print("\n=== FIVE FASTEST CONFIGURATIONS ===")

    for name, timing in fastest[:5]:
        print(
            f"{name}: {timing['total_seconds']:.4f} seconds "
            f"({timing['documents_ranked']} documents)"
        )

    print("\n=== FIVE SLOWEST CONFIGURATIONS ===")

    for name, timing in fastest[-5:][::-1]:
        print(
            f"{name}: {timing['total_seconds']:.4f} seconds "
            f"({timing['documents_ranked']} documents)"
        )

    for config in configurations:
        print(f"\n=== {config.name} ===")

        for result in results[config.name][:top_k]:
            print(
                f"{result.rank:>3}. "
                f"[{result.score:.6f}] "
                f"{result.app_id} — {result.game_title}"
            )

    print(f"\nReport saved to: {report_path}")

    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run and record all TF-IDF ranking configurations."
    )

    parser.add_argument(
        "query",
        nargs="?",
        default="worker placement",
        help="Search query (default: worker placement).",
    )

    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help="Path to the SQLite index.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON experiment reports.",
    )

    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of results saved and displayed per configuration.",
    )

    args = parser.parse_args()

    if args.top <= 0:
        parser.error("--top must be a positive integer.")

    run_experiment(
        database_path=args.database,
        query=args.query,
        top_k=args.top,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
