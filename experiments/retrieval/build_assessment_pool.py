
"""Build blinded, reproducible relevance-assessment pools."""

import ast
import csv
import hashlib
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path


REPORT_DIR = Path("data/experiment_results/formal_evaluation")
OUTPUT_DIR = Path("data/assessment/formal_evaluation")
SOURCE_DIR = Path("data/bgg_games")

TOP_K = 20
EXPECTED_CONFIGURATIONS = 30
RANDOM_SEED = 20261121

FORMAL_QUERIES = [
    ("Q01", "cooperative disease"),
    ("Q02", "medieval economic strategy"),
    ("Q03", "space exploration"),
    ("Q04", "deck building fantasy"),
    ("Q05", "hidden role deduction"),
    ("Q06", "civilization development"),
    ("Q07", "train route building"),
    ("Q08", "negotiation trading"),
    ("Q09", "solo adventure campaign"),
]

ASSESSMENT_FIELDS = [
    "assessment_id",
    "app_id",
    "game_title",
    "release_year",
    "short_description",
    "description",
    "game_type",
    "game_category",
    "game_mechanic",
    "designer",
    "publisher",
    "relevance_grade",
]

LIST_FIELDS = {
    "game_type",
    "game_category",
    "game_mechanic",
}


def sha256_file(path: Path) -> str:
    """Calculate a file's SHA-256 fingerprint."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def format_list_field(value: str) -> str:
    """Convert a serialized Python list into readable text."""
    if not value:
        return ""

    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value

    if isinstance(parsed, (list, tuple)):
        return "; ".join(str(item) for item in parsed)

    return str(parsed)


def load_reports():
    """Load and validate all nine formal experiment reports."""
    report_files = list(REPORT_DIR.glob("*.json"))

    if len(report_files) != len(FORMAL_QUERIES):
        raise ValueError(
            f"Expected 9 reports, found {len(report_files)}."
        )

    reports_by_query = {}

    for path in report_files:
        with path.open(encoding="utf-8") as file:
            report = json.load(file)

        query = report.get("query")

        if query in reports_by_query:
            raise ValueError(f"Duplicate report for query: {query}")

        reports_by_query[query] = (path, report)

    expected_queries = {query for _, query in FORMAL_QUERIES}

    if set(reports_by_query) != expected_queries:
        raise ValueError("Report queries do not match the formal query set.")

    fingerprints = set()

    for query_id, query in FORMAL_QUERIES:
        path, report = reports_by_query[query]

        if report["experiment"]["configuration_count"] != EXPECTED_CONFIGURATIONS:
            raise ValueError(f"{path.name}: incorrect configuration count.")

        if report["experiment"]["top_k"] != TOP_K:
            raise ValueError(f"{path.name}: expected top_k={TOP_K}.")

        configurations = report["configurations"]

        if len(configurations) != EXPECTED_CONFIGURATIONS:
            raise ValueError(f"{path.name}: incorrect configuration count.")

        for name, config in configurations.items():
            results = config.get("top_results", [])

            if len(results) != TOP_K:
                raise ValueError(
                    f"{path.name}, {name}: expected {TOP_K} results."
                )

            ranks = [result["rank"] for result in results]

            if sorted(ranks) != list(range(1, TOP_K + 1)):
                raise ValueError(
                    f"{path.name}, {name}: invalid result ranks."
                )

            for result in results:
                if not result.get("app_id"):
                    raise ValueError(f"{path.name}, {name}: missing app_id.")

                if not math.isfinite(result["score"]):
                    raise ValueError(f"{path.name}, {name}: invalid score.")

        fingerprint = (
            report["dataset"]["source_filename"],
            report["dataset"]["source_sha256"],
            report["dataset"]["document_count"],
            report["index"]["schema_version"],
            tuple(report["index"]["indexed_fields"]),
            report["index"]["tokenizer_pattern"],
        )

        fingerprints.add(fingerprint)

    if len(fingerprints) != 1:
        raise ValueError("Reports do not share identical dataset/index metadata.")

    return reports_by_query, fingerprints.pop()


def collect_pools(reports_by_query):
    """Collect unique documents and all their ranking appearances."""
    pools = {}

    for query_id, query in FORMAL_QUERIES:
        _, report = reports_by_query[query]

        documents = defaultdict(list)

        for config_name, config in report["configurations"].items():
            for result in config["top_results"]:
                app_id = str(result["app_id"])

                documents[app_id].append({
                    "configuration": config_name,
                    "rank": result["rank"],
                    "score": result["score"],
                })

        pools[query_id] = {
            "query": query,
            "documents": documents,
            "result_entries": sum(
                len(appearances)
                for appearances in documents.values()
            ),
        }

    return pools


def load_source_documents(source_path, required_ids):
    """Read and retain only documents included in the assessment pools."""
    documents = {}

    with source_path.open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file, delimiter="\t")

        for row in reader:
            app_id = row["app_id"]

            if app_id not in required_ids:
                continue

            if app_id in documents:
                raise ValueError(f"Duplicate source document ID: {app_id}")

            documents[app_id] = {
                field: (
                    format_list_field(row[field])
                    if field in LIST_FIELDS
                    else row[field]
                )
                for field in ASSESSMENT_FIELDS
                if field in row and field not in {
                    "assessment_id",
                    "app_id",
                    "relevance_grade",
                }
            }

    missing = required_ids - set(documents)

    if missing:
        raise ValueError(
            f"{len(missing)} pooled documents missing from source TSV: "
            f"{sorted(missing)[:10]}"
        )

    return documents


def write_json(path: Path, data):
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_assessment_files(pools, source_documents, source_metadata):
    """Write assessment TSVs, provenance files and a manifest."""
    provenance_dir = OUTPUT_DIR / "provenance"
    provenance_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "description": "Formal BGG relevance-assessment pools",
        "source_filename": source_metadata[0],
        "source_sha256": source_metadata[1],
        "document_count": source_metadata[2],
        "top_k_per_configuration": TOP_K,
        "configuration_count": EXPECTED_CONFIGURATIONS,
        "random_seed": RANDOM_SEED,
        "assessment_scale": {
            "0": "Not relevant",
            "1": "Partially relevant",
            "2": "Highly relevant",
        },
        "queries": [],
    }

    global_ids = set()

    for query_index, (query_id, query) in enumerate(FORMAL_QUERIES):
        pool = pools[query_id]
        documents = pool["documents"]

        # Shuffle deterministically and assign assessment IDs.
        ordered_ids = sorted(documents)
        rng = random.Random(RANDOM_SEED + query_index)
        rng.shuffle(ordered_ids)

        assessment_rows = []
        provenance_documents = []

        for position, app_id in enumerate(ordered_ids, start=1):
            assessment_id = f"{query_id}-{position:03d}"
            source = source_documents[app_id]

            row = {
                "assessment_id": assessment_id,
                "app_id": app_id,
                **source,
                "relevance_grade": "",
            }
            assessment_rows.append(row)

            appearances = sorted(
                documents[app_id],
                key=lambda item: (
                    item["configuration"],
                    item["rank"],
                ),
            )

            provenance_documents.append({
                "assessment_id": assessment_id,
                "app_id": app_id,
                "appearances": appearances,
            })

        slug = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")

        assessment_path = OUTPUT_DIR / f"{query_id}_{slug}.tsv"

        with assessment_path.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=ASSESSMENT_FIELDS,
                delimiter="\t",
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(assessment_rows)

        provenance_path = provenance_dir / f"{query_id}_provenance.json"

        write_json(provenance_path, {
            "query_id": query_id,
            "query": query,
            "documents": provenance_documents,
        })

        global_ids.update(documents)

        manifest["queries"].append({
            "query_id": query_id,
            "query": query,
            "report_filename": (
                # Filled from the matching formal report below.
                None
            ),
            "result_entries": pool["result_entries"],
            "unique_documents": len(documents),
            "assessment_file": assessment_path.name,
            "provenance_file": str(provenance_path.relative_to(OUTPUT_DIR)),
        })

        print(
            f"{query_id}: {len(documents)} unique games from "
            f"{pool['result_entries']} result entries."
        )

    manifest["total_unique_documents_across_queries"] = len(global_ids)

    write_json(OUTPUT_DIR / "manifest.json", manifest)

    return manifest


def main():
    print("=== BUILDING FORMAL ASSESSMENT POOLS ===")

    reports_by_query, fingerprint = load_reports()

    source_filename, expected_hash, document_count, *_ = fingerprint
    source_path = SOURCE_DIR / source_filename

    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    actual_hash = sha256_file(source_path)

    if actual_hash != expected_hash:
        raise ValueError("Source TSV SHA-256 does not match experiment reports.")

    print("PASS: All nine experiment reports validated.")
    print("PASS: Source dataset fingerprint verified.")

    pools = collect_pools(reports_by_query)

    required_ids = {
        app_id
        for pool in pools.values()
        for app_id in pool["documents"]
    }

    print(f"Unique games across all queries: {len(required_ids)}")

    source_documents = load_source_documents(
        source_path,
        required_ids,
    )

    print(f"PASS: Enriched {len(source_documents)} source records.")

    manifest = build_assessment_files(
        pools,
        source_documents,
        fingerprint[:3],
    )

    print("\n=== ASSESSMENT POOLS CREATED ===")
    print("Output directory:", OUTPUT_DIR)
    print("Queries:", len(manifest["queries"]))
    print(
        "Unique games across queries:",
        manifest["total_unique_documents_across_queries"],
    )


if __name__ == "__main__":
    main()
