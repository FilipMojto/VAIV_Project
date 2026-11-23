"""Evaluate Q01 retrieval rankings against the completed relevance judgments."""

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


RANKINGS_PATH = Path(
    "data/comparison_results/tfidf_vs_lucene/rankings_long.tsv"
)

ASSESSMENT_PATHS = [
    Path("data/assessment/completed/Q01_cooperative_disease.tsv"),
    Path(
        "data/assessment/lucene_extension_completed/"
        "Q01_cooperative_disease.tsv"
    ),
]

OUTPUT_DIR = Path("data/comparison_results/tfidf_vs_lucene")

QUERY_ID = "Q01"
QUERY_TEXT = "cooperative disease"
TOP_K = 10
EXPECTED_TFIDF_CONFIGURATIONS = 30
EXPECTED_SYSTEMS = EXPECTED_TFIDF_CONFIGURATIONS + 1


def sha256_file(path):
    """Calculate a file's SHA-256 fingerprint."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def read_tsv(path):
    """Read a UTF-8 TSV file."""

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")

        if reader.fieldnames is None:
            raise ValueError(f"Missing TSV header: {path}")

        return reader.fieldnames, list(reader)


def load_judgments():
    """Load and merge the original and Lucene-extension judgments."""

    judgments = {}
    titles = {}
    source_counts = {}

    for path in ASSESSMENT_PATHS:
        if not path.is_file():
            raise FileNotFoundError(path)

        fieldnames, rows = read_tsv(path)

        required = {"app_id", "game_title", "relevance_grade"}
        missing = required - set(fieldnames)

        if missing:
            raise ValueError(
                f"{path}: missing columns {sorted(missing)}"
            )

        source_counts[str(path)] = len(rows)

        for row in rows:
            app_id = str(row["app_id"]).strip()
            title = row["game_title"]
            grade_text = row["relevance_grade"]

            if not app_id:
                raise ValueError(f"{path}: empty app_id.")

            if app_id in judgments:
                raise ValueError(
                    f"Duplicate judgment for app_id {app_id}."
                )

            if grade_text not in {"0", "1", "2"}:
                raise ValueError(
                    f"{path}: invalid or missing grade "
                    f"'{grade_text}' for app_id {app_id}."
                )

            judgments[app_id] = int(grade_text)
            titles[app_id] = title

    if not judgments:
        raise ValueError("No relevance judgments were loaded.")

    return judgments, titles, source_counts


def load_rankings(judgments, judgment_titles):
    """Load Q01 rankings and validate all top-10 judgments."""

    if not RANKINGS_PATH.is_file():
        raise FileNotFoundError(RANKINGS_PATH)

    _, rows = read_tsv(RANKINGS_PATH)

    systems = defaultdict(list)
    query_texts = set()

    for row in rows:
        if row["query_id"] != QUERY_ID:
            continue

        query_texts.add(row["query"])

        system = row["retrieval_system"]
        configuration = row["configuration"]
        key = (system, configuration)

        app_id = str(row["app_id"]).strip()

        try:
            rank = int(row["rank"])
            score = float(row["score"])
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid rank or score for {key}, app_id {app_id}."
            ) from error

        if not math.isfinite(score):
            raise ValueError(
                f"Non-finite score for {key}, app_id {app_id}."
            )

        systems[key].append({
            "query_id": QUERY_ID,
            "query": row["query"],
            "retrieval_system": system,
            "configuration": configuration,
            "app_id": app_id,
            "game_title": row["game_title"],
            "rank": rank,
            "score": score,
        })

    if query_texts != {QUERY_TEXT}:
        raise ValueError(
            f"Unexpected Q01 query text: {query_texts}"
        )

    if len(systems) != EXPECTED_SYSTEMS:
        raise ValueError(
            f"Expected {EXPECTED_SYSTEMS} Q01 systems/configurations, "
            f"found {len(systems)}."
        )

    lucene_keys = [
        key for key in systems
        if key[0] == "lucene_bgg_only"
    ]

    if len(lucene_keys) != 1:
        raise ValueError(
            f"Expected exactly one Lucene BGG-only ranking, "
            f"found {len(lucene_keys)}."
        )

    tfidf_keys = [
        key for key in systems
        if key[0] == "tfidf"
    ]

    if len(tfidf_keys) != EXPECTED_TFIDF_CONFIGURATIONS:
        raise ValueError(
            f"Expected {EXPECTED_TFIDF_CONFIGURATIONS} TF-IDF "
            f"configurations, found {len(tfidf_keys)}."
        )

    top10_rows = []

    for key, results in systems.items():
        results.sort(key=lambda result: result["rank"])

        ranks = [result["rank"] for result in results]

        if ranks != list(range(1, len(results) + 1)):
            raise ValueError(
                f"{key}: ranks are missing, duplicated, or unordered."
            )

        app_ids = [result["app_id"] for result in results]

        if len(app_ids) != len(set(app_ids)):
            raise ValueError(f"{key}: duplicate app_id in ranking.")

        if len(results) < TOP_K:
            raise ValueError(f"{key}: fewer than {TOP_K} results.")

        for result in results[:TOP_K]:
            app_id = result["app_id"]

            if app_id not in judgments:
                raise ValueError(
                    f"{key}: top-{TOP_K} result "
                    f"{app_id} has no relevance judgment."
                )

            if (
                app_id in judgment_titles
                and result["game_title"] != judgment_titles[app_id]
            ):
                raise ValueError(
                    f"{key}: title mismatch for app_id {app_id}: "
                    f"{result['game_title']!r} != "
                    f"{judgment_titles[app_id]!r}"
                )

            grade = judgments[app_id]

            top10_rows.append({
                "query_id": QUERY_ID,
                "retrieval_system": result["retrieval_system"],
                "configuration": result["configuration"],
                "rank": result["rank"],
                "app_id": app_id,
                "game_title": result["game_title"],
                "score": result["score"],
                "relevance_grade": grade,
                "binary_relevant": int(grade > 0),
            })

    return systems, top10_rows


def dcg(grades):
    """Calculate discounted cumulative gain."""

    return sum(
        (2 ** grade - 1) / math.log2(rank + 1)
        for rank, grade in enumerate(grades, start=1)
    )


def evaluate_systems(systems, judgments):
    """Calculate Q01 relevance metrics for every system."""

    relevant_total = sum(
        grade > 0 for grade in judgments.values()
    )

    if relevant_total == 0:
        raise ValueError("No relevant documents in Q01 judgments.")

    ideal_grades = sorted(
        judgments.values(),
        reverse=True,
    )[:TOP_K]

    ideal_dcg = dcg(ideal_grades)

    if ideal_dcg == 0:
        raise ValueError("Ideal DCG is zero.")

    metric_rows = []

    for (system, configuration), results in sorted(systems.items()):
        top10 = results[:TOP_K]
        grades = [
            judgments[result["app_id"]]
            for result in top10
        ]

        relevant_in_top10 = sum(grade > 0 for grade in grades)
        highly_relevant_in_top10 = sum(grade == 2 for grade in grades)

        actual_dcg = dcg(grades)

        metric_rows.append({
            "query_id": QUERY_ID,
            "query": QUERY_TEXT,
            "retrieval_system": system,
            "configuration": configuration,
            "evaluated_at": TOP_K,
            "ndcg_at_10": actual_dcg / ideal_dcg,
            "precision_at_10": relevant_in_top10 / TOP_K,
            "recall_at_10": relevant_in_top10 / relevant_total,
            "relevant_in_top10": relevant_in_top10,
            "highly_relevant_in_top10": highly_relevant_in_top10,
            "judged_documents": len(judgments),
            "relevant_documents_in_pool": relevant_total,
        })

    return metric_rows


def write_tsv(path, rows):
    """Write a UTF-8-BOM TSV file."""

    if not rows:
        raise ValueError(f"Cannot write empty output: {path}")

    with path.open("w", encoding="utf-8-sig", newline="") as file:
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
        description="Evaluate Q01 rankings using completed relevance judgments."
    )

    parser.add_argument(
        "--write",
        action="store_true",
        help="Write evaluation files. Without this flag, perform a dry run.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Output directory.",
    )

    args = parser.parse_args()

    print("Loading Q01 relevance judgments...")
    judgments, judgment_titles, source_counts = load_judgments()

    grade_counts = Counter(judgments.values())
    relevant_total = sum(
        grade > 0 for grade in judgments.values()
    )

    print("Loading Q01 rankings...")
    systems, top10_rows = load_rankings(
        judgments,
        judgment_titles,
    )

    metric_rows = evaluate_systems(systems, judgments)

    if len(metric_rows) != EXPECTED_SYSTEMS:
        raise ValueError("Unexpected number of evaluation rows.")

    if len(top10_rows) != EXPECTED_SYSTEMS * TOP_K:
        raise ValueError("Unexpected number of top-10 judgment rows.")

    print("\n=== Q01 RELEVANCE EVALUATION ===")
    print(f"Judged documents: {len(judgments)}")
    print(f"Grade distribution: {dict(sorted(grade_counts.items()))}")
    print(f"Relevant documents (grade > 0): {relevant_total}")
    print(f"TF-IDF configurations: {EXPECTED_TFIDF_CONFIGURATIONS}")
    print("Lucene systems: 1")
    print(f"Systems evaluated: {len(metric_rows)}")
    print(f"Top-10 results evaluated: {len(top10_rows)}")
    print("All top-10 results have relevance judgments.")

    print("\n=== TOP CONFIGURATIONS BY NDCG@10 ===")

    for row in sorted(
        metric_rows,
        key=lambda item: item["ndcg_at_10"],
        reverse=True,
    )[:5]:
        print(
            f'{row["configuration"]}: '
            f'nDCG@10={row["ndcg_at_10"]:.4f}, '
            f'P@10={row["precision_at_10"]:.3f}, '
            f'Recall@10={row["recall_at_10"]:.3f}'
        )

    lucene_row = next(
        row for row in metric_rows
        if row["retrieval_system"] == "lucene_bgg_only"
    )

    print("\n=== LUCENE BM25 ===")
    print(
        f'nDCG@10={lucene_row["ndcg_at_10"]:.4f}, '
        f'P@10={lucene_row["precision_at_10"]:.3f}, '
        f'Recall@10={lucene_row["recall_at_10"]:.3f}'
    )

    if not args.write:
        print("\nDRY RUN: no files written.")
        print("Use --write to generate the evaluation files.")
        return

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = output_dir / "q01_relevance_metrics.tsv"
    top10_path = output_dir / "q01_top10_judgments.tsv"
    manifest_path = output_dir / "q01_relevance_manifest.json"

    write_tsv(metrics_path, metric_rows)
    write_tsv(top10_path, top10_rows)

    manifest = {
        "created_at": datetime.now().astimezone().isoformat(),
        "query": {
            "id": QUERY_ID,
            "text": QUERY_TEXT,
        },
        "evaluation": {
            "systems_evaluated": len(metric_rows),
            "tfidf_configurations": EXPECTED_TFIDF_CONFIGURATIONS,
            "lucene_system": "lucene_bgg_only",
            "top_k": TOP_K,
            "metrics": {
                "ndcg_at_10": (
                    "Graded relevance; gain = 2^grade - 1; "
                    "logarithmic discount; ideal ranking based on "
                    "all judged Q01 documents."
                ),
                "precision_at_10": (
                    "Number of top-10 results with relevance grade "
                    "greater than zero, divided by 10."
                ),
                "recall_at_10": (
                    "Number of relevant top-10 results divided by "
                    "the number of relevant documents in the "
                    "combined Q01 assessment pool."
                ),
            },
            "binary_relevance_threshold": 1,
            "relevance_grades": {
                "0": "Not relevant",
                "1": "Partially relevant",
                "2": "Highly relevant",
            },
            "scope_limitation": (
                "Recall is assessment-pool recall, not collection-wide "
                "recall. Results are evaluated against the 64 judged "
                "documents in the combined Q01 assessment pool."
            ),
        },
        "judgments": {
            "document_count": len(judgments),
            "grade_distribution": {
                str(grade): count
                for grade, count in sorted(grade_counts.items())
            },
            "relevant_document_count": relevant_total,
            "source_files": [
                {
                    "path": str(path),
                    "sha256": sha256_file(path),
                    "row_count": source_counts[str(path)],
                }
                for path in ASSESSMENT_PATHS
            ],
        },
        "ranking_input": {
            "path": str(RANKINGS_PATH),
            "sha256": sha256_file(RANKINGS_PATH),
        },
        "outputs": [
            str(metrics_path),
            str(top10_path),
            str(manifest_path),
        ],
    }

    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, ensure_ascii=False)
        file.write("\n")

    print("\nEvaluation files written to:", output_dir)
    print(" ", metrics_path.name)
    print(" ", top10_path.name)
    print(" ", manifest_path.name)


if __name__ == "__main__":
    main()
