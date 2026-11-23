
"""Compare formal TF-IDF configurations against Lucene BM25 rankings."""

import argparse
import csv
import hashlib
import json
import math
import statistics
from datetime import datetime
from pathlib import Path

from experiments.retrieval.build_assessment_pool import (
    FORMAL_QUERIES,
    TOP_K,
)


TFIDF_DIR = Path("data/experiment_results/formal_evaluation")
LUCENE_BGG_DIR = Path("data/lucene_experiment_results/bgg_only")
LUCENE_ENRICHED_DIR = Path("data/lucene_experiment_results/enriched")

OUTPUT_DIR = Path("data/comparison_results/tfidf_vs_lucene")

EXPECTED_CONFIGURATIONS = 30
EXPECTED_DOCUMENT_COUNT = 17648


def sha256_file(path):
    """Calculate a file's SHA-256 fingerprint."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def load_json(path):
    """Load a JSON report."""

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def validate_results(results, label):
    """Validate a top-k result list and return it indexed by app_id."""

    if len(results) != TOP_K:
        raise ValueError(
            f"{label}: expected {TOP_K} results, found {len(results)}."
        )

    ranks = [result["rank"] for result in results]
    if sorted(ranks) != list(range(1, TOP_K + 1)):
        raise ValueError(f"{label}: invalid or missing ranks.")

    indexed = {}

    for result in results:
        app_id = str(result["app_id"])

        if not app_id:
            raise ValueError(f"{label}: missing app_id.")

        if app_id in indexed:
            raise ValueError(f"{label}: duplicate app_id {app_id}.")

        if not math.isfinite(result["score"]):
            raise ValueError(f"{label}: invalid score for {app_id}.")

        indexed[app_id] = result

    return indexed


def load_tfidf_reports():
    """Load and validate the nine TF-IDF reports."""

    paths = list(TFIDF_DIR.glob("*.json"))

    if len(paths) != len(FORMAL_QUERIES):
        raise ValueError(
            f"Expected {len(FORMAL_QUERIES)} TF-IDF reports, "
            f"found {len(paths)}."
        )

    reports = {}
    fingerprints = set()
    configuration_names = None

    for path in paths:
        report = load_json(path)
        query = report["query"]

        if query in reports:
            raise ValueError(f"Duplicate TF-IDF report for {query}.")

        if report["dataset"]["document_count"] != str(
            EXPECTED_DOCUMENT_COUNT
        ):
            raise ValueError(f"{path.name}: unexpected document count.")

        fingerprints.add(report["dataset"]["source_sha256"])

        if report["experiment"]["top_k"] != TOP_K:
            raise ValueError(f"{path.name}: unexpected top_k.")

        configurations = report["configurations"]

        if len(configurations) != EXPECTED_CONFIGURATIONS:
            raise ValueError(
                f"{path.name}: expected {EXPECTED_CONFIGURATIONS} "
                f"configurations."
            )

        current_names = set(configurations)

        if configuration_names is None:
            configuration_names = current_names
        elif current_names != configuration_names:
            raise ValueError(
                f"{path.name}: configuration set differs from other reports."
            )

        for name, config in configurations.items():
            validate_results(
                config["top_results"],
                f"{path.name}, {name}",
            )

        reports[query] = (path, report)

    expected_queries = {query for _, query in FORMAL_QUERIES}

    if set(reports) != expected_queries:
        raise ValueError("TF-IDF reports do not match the formal queries.")

    if len(fingerprints) != 1:
        raise ValueError("TF-IDF reports use different source datasets.")

    return reports, configuration_names, next(iter(fingerprints))


def load_lucene_reports(directory, index_type):
    """Load and validate one set of nine Lucene reports."""

    paths = list(directory.glob("*.json"))

    if len(paths) != len(FORMAL_QUERIES):
        raise ValueError(
            f"{index_type}: expected {len(FORMAL_QUERIES)} reports, "
            f"found {len(paths)}."
        )

    reports = {}

    for path in paths:
        report = load_json(path)
        query = report["query"]["text"]
        query_id = report["query"]["id"]

        if query in reports:
            raise ValueError(f"{index_type}: duplicate query {query}.")

        if report["query"]["id"] != query_id:
            raise ValueError(f"{path.name}: invalid query ID.")

        if report["index"]["type"] != index_type:
            raise ValueError(f"{path.name}: incorrect index type.")

        if report["dataset"]["document_count"] != EXPECTED_DOCUMENT_COUNT:
            raise ValueError(f"{path.name}: unexpected document count.")

        if report["experiment"]["top_k"] != TOP_K:
            raise ValueError(f"{path.name}: unexpected top_k.")

        validate_results(report["top_results"], path.name)

        reports[query] = (path, report)

    expected_queries = {query for _, query in FORMAL_QUERIES}

    if set(reports) != expected_queries:
        raise ValueError(
            f"{index_type}: reports do not match the formal queries."
        )

    return reports


def validate_enriched_equivalence(bgg_reports, enriched_reports):
    """Verify whether enriched and BGG-only rankings are identical."""

    for _, query in FORMAL_QUERIES:
        bgg_path, bgg = bgg_reports[query]
        enriched_path, enriched = enriched_reports[query]

        bgg_results = bgg["top_results"]
        enriched_results = enriched["top_results"]

        if len(bgg_results) != len(enriched_results):
            raise ValueError(
                f"{query}: Lucene result counts differ."
            )

        for first, second in zip(bgg_results, enriched_results):
            if (
                first["rank"] != second["rank"]
                or str(first["app_id"]) != str(second["app_id"])
                or first["game_title"] != second["game_title"]
                or not math.isclose(
                    first["score"],
                    second["score"],
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                )
            ):
                raise ValueError(
                    f"{query}: enriched and BGG-only results differ "
                    f"at rank {first['rank']}."
                )


def spearman_correlation(first_ranks, second_ranks):
    """Calculate Spearman's rho for shared documents."""

    if len(first_ranks) < 2:
        return None

    def ordinal_ranks(values):
        ordered = sorted(
            range(len(values)),
            key=lambda index: values[index],
        )
        ranks = [0] * len(values)

        for rank, index in enumerate(ordered, start=1):
            ranks[index] = rank

        return ranks

    first = ordinal_ranks(first_ranks)
    second = ordinal_ranks(second_ranks)

    count = len(first)
    differences = [
        a - b for a, b in zip(first, second)
    ]

    sum_squared = sum(value ** 2 for value in differences)

    return 1 - (
        6 * sum_squared / (count * (count ** 2 - 1))
    )


def kendall_tau(first_ranks, second_ranks):
    """Calculate Kendall's tau-b for shared documents."""

    count = len(first_ranks)

    if count < 2:
        return None

    concordant = 0
    discordant = 0

    for i in range(count):
        for j in range(i + 1, count):
            first_difference = first_ranks[i] - first_ranks[j]
            second_difference = second_ranks[i] - second_ranks[j]

            product = first_difference * second_difference

            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1

    pairs = count * (count - 1) / 2

    return (concordant - discordant) / pairs


def compare_rankings(tfidf_results, lucene_results):
    """Calculate overlap and rank correlation between two rankings."""

    common_ids = sorted(
        set(tfidf_results) & set(lucene_results)
    )

    tfidf_ranks = [
        tfidf_results[app_id]["rank"] for app_id in common_ids
    ]
    lucene_ranks = [
        lucene_results[app_id]["rank"] for app_id in common_ids
    ]

    top10_tfidf = {
        app_id
        for app_id, result in tfidf_results.items()
        if result["rank"] <= 10
    }
    top10_lucene = {
        app_id
        for app_id, result in lucene_results.items()
        if result["rank"] <= 10
    }

    top20_tfidf = set(tfidf_results)
    top20_lucene = set(lucene_results)

    top10_overlap = len(top10_tfidf & top10_lucene)
    top20_overlap = len(top20_tfidf & top20_lucene)
    top20_union = len(top20_tfidf | top20_lucene)

    return {
        "shared_documents": len(common_ids),
        "top10_overlap": top10_overlap,
        "top10_overlap_fraction": top10_overlap / 10,
        "top20_overlap": top20_overlap,
        "top20_jaccard": top20_overlap / top20_union,
        "spearman_rho": spearman_correlation(
            tfidf_ranks,
            lucene_ranks,
        ),
        "kendall_tau": kendall_tau(
            tfidf_ranks,
            lucene_ranks,
        ),
    }


def build_long_rows(tfidf_reports, lucene_reports):
    """Build a row for every ranked result."""

    rows = []

    for query_id, query in FORMAL_QUERIES:
        _, report = tfidf_reports[query]

        for config_name, config in report["configurations"].items():
            for result in config["top_results"]:
                rows.append({
                    "query_id": query_id,
                    "query": query,
                    "retrieval_system": "tfidf",
                    "configuration": config_name,
                    "tf_method": config["tf_method"],
                    "idf_method": config["idf_method"],
                    "normalization": config["normalization"],
                    "app_id": str(result["app_id"]),
                    "game_title": result["game_title"],
                    "rank": result["rank"],
                    "score": result["score"],
                })

        _, lucene_report = lucene_reports[query]

        for result in lucene_report["top_results"]:
            rows.append({
                "query_id": query_id,
                "query": query,
                "retrieval_system": "lucene_bgg_only",
                "configuration": "BM25_k1_1.2_b_0.75",
                "tf_method": "",
                "idf_method": "",
                "normalization": "",
                "app_id": str(result["app_id"]),
                "game_title": result["game_title"],
                "rank": result["rank"],
                "score": result["score"],
            })

    return rows


def build_comparison_rows(tfidf_reports, lucene_reports):
    """Compare each TF-IDF configuration against Lucene per query."""

    rows = []

    for query_id, query in FORMAL_QUERIES:
        _, report = tfidf_reports[query]
        _, lucene_report = lucene_reports[query]

        lucene_results = {
            str(result["app_id"]): result
            for result in lucene_report["top_results"]
        }

        for config_name, config in report["configurations"].items():
            tfidf_results = {
                str(result["app_id"]): result
                for result in config["top_results"]
            }

            metrics = compare_rankings(
                tfidf_results,
                lucene_results,
            )

            rows.append({
                "query_id": query_id,
                "query": query,
                "configuration": config_name,
                "tf_method": config["tf_method"],
                "idf_method": config["idf_method"],
                "normalization": config["normalization"],
                **metrics,
            })

    return rows


def build_summary_rows(comparison_rows):
    """Aggregate each configuration's comparison across queries."""

    configurations = sorted({
        row["configuration"] for row in comparison_rows
    })

    summary = []

    metric_names = [
        "shared_documents",
        "top10_overlap",
        "top10_overlap_fraction",
        "top20_overlap",
        "top20_jaccard",
        "spearman_rho",
        "kendall_tau",
    ]

    for name in configurations:
        rows = [
            row for row in comparison_rows
            if row["configuration"] == name
        ]

        output = {
            "configuration": name,
            "tf_method": rows[0]["tf_method"],
            "idf_method": rows[0]["idf_method"],
            "normalization": rows[0]["normalization"],
            "query_count": len(rows),
        }

        for metric in metric_names:
            values = [
                row[metric]
                for row in rows
                if row[metric] is not None
            ]

            output[f"mean_{metric}"] = (
                statistics.mean(values) if values else None
            )

        summary.append(output)

    return summary


def write_tsv(path, rows):
    """Write a TSV file using the first row's field order."""

    if not rows:
        raise ValueError(f"Cannot write empty output: {path}")

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0]),
            delimiter="\t",
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Compare TF-IDF configurations against Lucene BM25."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write comparison files. Without this flag, perform a dry run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Comparison output directory.",
    )

    args = parser.parse_args()

    print("Loading TF-IDF reports...")
    tfidf_reports, configurations, dataset_hash = load_tfidf_reports()

    print("Loading Lucene BGG-only reports...")
    lucene_reports = load_lucene_reports(
        LUCENE_BGG_DIR,
        "bgg_only",
    )

    print("Loading Lucene enriched reports...")
    enriched_reports = load_lucene_reports(
        LUCENE_ENRICHED_DIR,
        "enriched",
    )

    print("Validating enriched/BGG-only equivalence...")
    validate_enriched_equivalence(
        lucene_reports,
        enriched_reports,
    )

    long_rows = build_long_rows(
        tfidf_reports,
        lucene_reports,
    )

    comparison_rows = build_comparison_rows(
        tfidf_reports,
        lucene_reports,
    )

    summary_rows = build_summary_rows(comparison_rows)

    expected_long_rows = (
        len(FORMAL_QUERIES)
        * (EXPECTED_CONFIGURATIONS + 1)
        * TOP_K
    )

    expected_comparison_rows = (
        len(FORMAL_QUERIES) * EXPECTED_CONFIGURATIONS
    )

    if len(long_rows) != expected_long_rows:
        raise ValueError("Unexpected number of long-format ranking rows.")

    if len(comparison_rows) != expected_comparison_rows:
        raise ValueError("Unexpected number of comparison rows.")

    print("\n=== VALIDATION SUMMARY ===")
    print(f"Queries: {len(FORMAL_QUERIES)}")
    print(f"TF-IDF configurations: {len(configurations)}")
    print(f"TF-IDF ranking entries: {len(FORMAL_QUERIES) * EXPECTED_CONFIGURATIONS * TOP_K}")
    print(f"Lucene ranking entries: {len(FORMAL_QUERIES) * TOP_K}")
    print(f"Total long-format rows: {len(long_rows)}")
    print(f"Configuration comparison rows: {len(comparison_rows)}")
    print(f"Configuration summary rows: {len(summary_rows)}")
    print("Enriched/BGG-only rankings and scores: identical")
    print(f"Dataset SHA-256: {dataset_hash}")

    if not args.write:
        print("\nDRY RUN: no files written.")
        print("Use --write to generate the comparison files.")
        return

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    write_tsv(output_dir / "rankings_long.tsv", long_rows)
    write_tsv(
        output_dir / "configuration_comparison.tsv",
        comparison_rows,
    )
    write_tsv(
        output_dir / "configuration_summary.tsv",
        summary_rows,
    )

    input_files = []

    for directory in (
        TFIDF_DIR,
        LUCENE_BGG_DIR,
        LUCENE_ENRICHED_DIR,
    ):
        for path in sorted(directory.glob("*.json")):
            input_files.append({
                "path": str(path),
                "sha256": sha256_file(path),
            })

    manifest = {
        "created_at": datetime.now().astimezone().isoformat(),
        "comparison": {
            "tfidf_configuration_count": len(configurations),
            "lucene_system": "bgg_only",
            "lucene_model": "BM25",
            "bm25_k1": 1.2,
            "bm25_b": 0.75,
            "top_k": TOP_K,
            "query_count": len(FORMAL_QUERIES),
            "spearman_and_kendall_scope": (
                "Documents shared by the two top-20 rankings; "
                "correlation measures ordering agreement only."
            ),
        },
        "dataset": {
            "document_count": EXPECTED_DOCUMENT_COUNT,
            "source_sha256": dataset_hash,
        },
        "enriched_validation": {
            "validated": True,
            "result": "Identical top-20 rankings and scores for all queries.",
            "note": (
                "The enriched index is not included as a separate "
                "ranking system because its current results are identical."
            ),
        },
        "inputs": input_files,
        "outputs": [
            "rankings_long.tsv",
            "configuration_comparison.tsv",
            "configuration_summary.tsv",
        ],
    }

    manifest_path = output_dir / "manifest.json"

    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, ensure_ascii=False)

    print(f"\nComparison files written to: {output_dir}")
    for filename in (
        "rankings_long.tsv",
        "configuration_comparison.tsv",
        "configuration_summary.tsv",
        "manifest.json",
    ):
        print(f"  {filename}")


if __name__ == "__main__":
    main()
