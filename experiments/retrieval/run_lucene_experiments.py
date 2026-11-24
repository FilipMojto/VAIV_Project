
"""Run formal BM25 retrieval experiments using Apache Lucene."""

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from time import perf_counter

from experiments.retrieval.build_assessment_pool import (
    FORMAL_QUERIES,
    TOP_K,
)
from src.lucene.search import LuceneSearcher


INDEX_CONFIGURATIONS = {
    "bgg_only": {
        "path": Path("data/indexes/lucene_aligned/lucene_bgg"),
        "output_dir": Path("data/lucene_experiment_results/bgg_only"),
    },
    "enriched": {
        "path": Path("data/indexes/lucene_aligned/lucene_enriched"),
        "output_dir": Path("data/lucene_experiment_results/enriched"),
    },
}

SEARCH_FIELD = "bgg_all_text"
SEARCH_OPERATOR = "OR"
BM25_K1 = 1.2
BM25_B = 0.75
ANALYZER_PATTERN = r"\b[a-zA-Z]{3,}\b"


def save_report(report: dict, query: str, output_dir: Path) -> Path:
    """Save a query report using a timestamped filename."""

    output_dir.mkdir(parents=True, exist_ok=True)

    query_slug = re.sub(
        r"[^a-z0-9]+",
        "_",
        query.lower(),
    ).strip("_")

    timestamp = datetime.now().astimezone().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    output_path = output_dir / f"{query_slug}_{timestamp}.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output_path


def run_experiments(index_type: str) -> None:
    """Run all formal queries against one Lucene index."""

    configuration = INDEX_CONFIGURATIONS[index_type]
    index_path = configuration["path"]
    output_dir = configuration["output_dir"]

    if not index_path.exists():
        raise FileNotFoundError(
            f"Lucene index does not exist: {index_path}"
        )

    print("=" * 60)
    print(f"Lucene experiment: {index_type}")
    print(f"Index: {index_path}")
    print(f"Output: {output_dir}")
    print("=" * 60)

    setup_start = perf_counter()

    with LuceneSearcher(index_path) as searcher:
        index_open_seconds = perf_counter() - setup_start
        document_count = searcher.document_count

        print(f"Documents indexed: {document_count}")
        print(f"Index opened in: {index_open_seconds:.4f} seconds")

        for query_id, query_text in FORMAL_QUERIES:
            print(f"\n[{query_id}] Query: {query_text}")

            query_start = perf_counter()

            search_response = searcher.search_text(
                query_text=query_text,
                field=SEARCH_FIELD,
                operator=SEARCH_OPERATOR,
                limit=TOP_K,
            )

            search_seconds = perf_counter() - query_start

            results = search_response["results"]
            total_hits = search_response["total_hits"]

            if len(results) != TOP_K:
                raise RuntimeError(
                    f"{query_id}: expected {TOP_K} results, "
                    f"received {len(results)}."
                )

            top_results = []

            for rank, result in enumerate(results, start=1):
                score = result["score"]

                if not result["app_id"]:
                    raise ValueError(
                        f"{query_id}: result at rank {rank} "
                        "has no app_id."
                    )

                if not math.isfinite(score):
                    raise ValueError(
                        f"{query_id}: invalid score at rank {rank}."
                    )

                top_results.append({
                    "rank": rank,
                    "app_id": result["app_id"],
                    "game_title": result["game_title"],
                    "score": score,
                })

            report = {
                "created_at": datetime.now().astimezone().isoformat(),
                "query": {
                    "id": query_id,
                    "text": query_text,
                },
                "dataset": {
                    "document_count": document_count,
                },
                "index": {
                    "type": index_type,
                    "path": str(index_path),
                    "field": SEARCH_FIELD,
                    "analyzer": {
                        "type": "CustomAnalyzer",
                        "tokenizer": "PatternTokenizer",
                        "pattern": ANALYZER_PATTERN,
                        "token_filter": "LowerCaseFilter",
                    },
                    "similarity": {
                        "type": "BM25",
                        "k1": BM25_K1,
                        "b": BM25_B,
                    },
                },
                "experiment": {
                    "operator": SEARCH_OPERATOR,
                    "top_k": TOP_K,
                    "total_hits": total_hits,
                },
                "timings": {
                    "index_open_seconds": index_open_seconds,
                    "search_seconds": search_seconds,
                },
                "top_results": top_results,
            }

            report_path = save_report(
                report,
                query_text,
                output_dir,
            )

            print(f"  Total hits: {total_hits}")
            print(f"  Search time: {search_seconds:.4f} seconds")
            print(f"  Top results: {len(top_results)}")
            print(f"  Report: {report_path}")

    print("\n" + "=" * 60)
    print(f"Completed {len(FORMAL_QUERIES)} queries for {index_type}.")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run formal Lucene BM25 retrieval experiments."
    )

    parser.add_argument(
        "--index",
        choices=INDEX_CONFIGURATIONS,
        required=True,
        help="Lucene index to evaluate.",
    )

    args = parser.parse_args()
    run_experiments(args.index)


if __name__ == "__main__":
    main()
