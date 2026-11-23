
"""Build a separate relevance-assessment extension from Lucene results."""

import argparse
import ast
import csv
import hashlib
import json
import random
import re
from collections import defaultdict
from pathlib import Path


LUCENE_RESULT_DIR = Path("data/lucene_experiment_results")
ORIGINAL_POOL_DIR = Path("data/assessment/formal_evaluation")
ORIGINAL_MANIFEST = ORIGINAL_POOL_DIR / "manifest.json"
SOURCE_DIR = Path("data/bgg_games")
OUTPUT_DIR = Path("data/assessment/lucene_extension")

SYSTEMS = ("bgg_only", "enriched")
TOP_K = 20
RANDOM_SEED = 20261123

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


def sha256_file(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def write_json(path, data):
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def format_list_field(value):
    if not value:
        return ""

    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value

    if isinstance(parsed, (list, tuple)):
        return "; ".join(str(item) for item in parsed)

    return str(parsed)


def query_slug(query):
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        query.lower(),
    ).strip("_")


def load_source_metadata():
    """Verify the BGG source against the original assessment manifest."""

    manifest = json.loads(
        ORIGINAL_MANIFEST.read_text(encoding="utf-8")
    )

    filename = manifest["source_filename"]
    expected_hash = manifest["source_sha256"]
    document_count = manifest["document_count"]

    source_path = SOURCE_DIR / filename

    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    actual_hash = sha256_file(source_path)

    if actual_hash != expected_hash:
        raise ValueError(
            "BGG source TSV SHA-256 differs from the original "
            "assessment manifest."
        )

    return {
        "filename": filename,
        "sha256": actual_hash,
        "document_count": document_count,
        "path": source_path,
    }


def load_original_pool_ids():
    """Load existing assessment IDs, separately for each query."""

    existing = {}

    for query_id, query in FORMAL_QUERIES:
        filename = f"{query_id}_{query_slug(query)}.tsv"
        path = ORIGINAL_POOL_DIR / filename

        if not path.is_file():
            raise FileNotFoundError(path)

        with path.open(
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file, delimiter="\t")

            if not reader.fieldnames or "app_id" not in reader.fieldnames:
                raise ValueError(f"Invalid assessment TSV: {path}")

            ids = [str(row["app_id"]) for row in reader]

        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate app_id in {path}")

        existing[query_id] = set(ids)

    return existing


def load_lucene_reports():
    """Load and validate all reports from both Lucene systems."""

    reports = {}

    for system in SYSTEMS:
        system_dir = LUCENE_RESULT_DIR / system
        paths = sorted(system_dir.glob("*.json"))

        if len(paths) != len(FORMAL_QUERIES):
            raise ValueError(
                f"{system}: expected {len(FORMAL_QUERIES)} reports, "
                f"found {len(paths)}."
            )

        reports[system] = {}

        for path in paths:
            report = json.loads(path.read_text(encoding="utf-8"))

            query = report["query"]
            query_id = query["id"]

            if query_id in reports[system]:
                raise ValueError(
                    f"{system}: duplicate report for {query_id}"
                )

            expected = {
                query_id: text
                for query_id, text in FORMAL_QUERIES
            }

            if query_id not in expected or query["text"] != expected[query_id]:
                raise ValueError(
                    f"{path}: unexpected query ID or query text."
                )

            if report["index"]["field"] != "bgg_all_text":
                raise ValueError(
                    f"{path}: unexpected search field."
                )

            if report["experiment"]["top_k"] != TOP_K:
                raise ValueError(
                    f"{path}: expected top_k={TOP_K}."
                )

            results = report["top_results"]

            if len(results) != TOP_K:
                raise ValueError(
                    f"{path}: expected {TOP_K} top results."
                )

            ranks = [item["rank"] for item in results]

            if sorted(ranks) != list(range(1, TOP_K + 1)):
                raise ValueError(f"{path}: invalid result ranks.")

            app_ids = [str(item["app_id"]) for item in results]

            if len(app_ids) != len(set(app_ids)):
                raise ValueError(f"{path}: duplicate app_id in results.")

            for item in results:
                if not item.get("app_id") or not item.get("game_title"):
                    raise ValueError(f"{path}: incomplete result.")

                if not isinstance(item.get("score"), (int, float)):
                    raise ValueError(f"{path}: invalid score.")

            reports[system][query_id] = {
                "path": path,
                "report": report,
            }

        expected_ids = {query_id for query_id, _ in FORMAL_QUERIES}

        if set(reports[system]) != expected_ids:
            raise ValueError(
                f"{system}: report query set does not match formal queries."
            )

    return reports


def compare_system_results(reports):
    """Report whether the two Lucene systems have identical top-20 results."""

    comparisons = {}

    for query_id, _ in FORMAL_QUERIES:
        system_results = {}

        for system in SYSTEMS:
            report = reports[system][query_id]["report"]

            system_results[system] = {
                str(item["app_id"]): item
                for item in report["top_results"]
            }

        bgg = reports["bgg_only"][query_id]["report"]["top_results"]
        enriched = reports["enriched"][query_id]["report"]["top_results"]

        same_order = [
            str(item["app_id"]) for item in bgg
        ] == [
            str(item["app_id"]) for item in enriched
        ]

        same_scores = all(
            left["score"] == right["score"]
            for left, right in zip(bgg, enriched)
        )

        comparisons[query_id] = {
            "same_order": same_order,
            "same_scores": same_scores,
            "same_top20": same_order and same_scores,
        }

    return comparisons


def collect_new_documents(reports, existing_ids):
    """Collect the union of Lucene results absent from original pools."""

    new_documents = {}

    for query_id, _ in FORMAL_QUERIES:
        appearances = defaultdict(list)

        for system in SYSTEMS:
            report_info = reports[system][query_id]
            report = report_info["report"]

            for item in report["top_results"]:
                app_id = str(item["app_id"])

                if app_id in existing_ids[query_id]:
                    continue

                appearances[app_id].append({
                    "system": system,
                    "rank": item["rank"],
                    "score": item["score"],
                    "game_title": item["game_title"],
                    "report_filename": report_info["path"].name,
                    "index_path": report["index"]["path"],
                })

        if appearances:
            new_documents[query_id] = appearances

    return new_documents


def load_source_documents(source_path, required_ids):
    """Read only the BGG records needed for the extension."""

    documents = {}

    with source_path.open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file, delimiter="\t")

        missing_fields = set(ASSESSMENT_FIELDS) - {
            "assessment_id",
            "app_id",
            "relevance_grade",
        } - set(reader.fieldnames or [])

        if missing_fields:
            raise ValueError(
                f"Source TSV is missing fields: {sorted(missing_fields)}"
            )

        for row in reader:
            app_id = str(row["app_id"])

            if app_id not in required_ids:
                continue

            if app_id in documents:
                raise ValueError(
                    f"Duplicate source document ID: {app_id}"
                )

            documents[app_id] = {
                field: (
                    format_list_field(row[field])
                    if field in LIST_FIELDS
                    else row[field]
                )
                for field in ASSESSMENT_FIELDS
                if field not in {
                    "assessment_id",
                    "app_id",
                    "relevance_grade",
                }
            }

    missing = required_ids - set(documents)

    if missing:
        raise ValueError(
            f"{len(missing)} Lucene documents missing from BGG TSV: "
            f"{sorted(missing)}"
        )

    return documents


def prepare_output(new_documents, source_documents, reports):
    """Prepare assessment TSVs, provenance and manifest in memory."""

    output_files = {}
    manifest = {
        "description": (
            "Additional relevance-assessment documents retrieved by "
            "the Lucene experiments but absent from the original "
            "TF-IDF assessment pools."
        ),
        "source": {
            "filename": SOURCE_METADATA["filename"],
            "sha256": SOURCE_METADATA["sha256"],
            "document_count": SOURCE_METADATA["document_count"],
        },
        "systems": list(SYSTEMS),
        "top_k_per_system": TOP_K,
        "random_seed": RANDOM_SEED,
        "assessment_scale": {
            "0": "Not relevant",
            "1": "Partially relevant",
            "2": "Highly relevant",
        },
        "queries": [],
    }

    for query_index, (query_id, query) in enumerate(FORMAL_QUERIES):
        documents = new_documents.get(query_id, {})

        if not documents:
            continue

        ordered_ids = sorted(documents)
        rng = random.Random(RANDOM_SEED + query_index)
        rng.shuffle(ordered_ids)

        rows = []
        provenance_documents = []

        for position, app_id in enumerate(ordered_ids, start=1):
            assessment_id = f"LX-{query_id}-{position:03d}"

            rows.append({
                "assessment_id": assessment_id,
                "app_id": app_id,
                **source_documents[app_id],
                "relevance_grade": "",
            })

            provenance_documents.append({
                "assessment_id": assessment_id,
                "app_id": app_id,
                "appearances": sorted(
                    documents[app_id],
                    key=lambda item: (
                        item["system"],
                        item["rank"],
                    ),
                ),
            })

        slug = query_slug(query)
        assessment_filename = f"{query_id}_{slug}.tsv"
        provenance_filename = f"{query_id}_provenance.json"

        output_files[assessment_filename] = {
            "type": "tsv",
            "fieldnames": ASSESSMENT_FIELDS,
            "rows": rows,
        }

        output_files[f"provenance/{provenance_filename}"] = {
            "type": "json",
            "data": {
                "query_id": query_id,
                "query": query,
                "documents": provenance_documents,
            },
        }

        manifest["queries"].append({
            "query_id": query_id,
            "query": query,
            "unique_new_documents": len(rows),
            "assessment_file": assessment_filename,
            "provenance_file": f"provenance/{provenance_filename}",
            "reports": {
                system: reports[system][query_id]["path"].name
                for system in SYSTEMS
            },
        })

    manifest["total_new_documents_across_queries"] = sum(
        item["unique_new_documents"]
        for item in manifest["queries"]
    )

    output_files["manifest.json"] = {
        "type": "json",
        "data": manifest,
    }

    return output_files, manifest


def write_output(output_files):
    """Write all extension files, refusing to overwrite existing output."""

    if OUTPUT_DIR.exists():
        raise FileExistsError(
            f"Output directory already exists: {OUTPUT_DIR}. "
            "Inspect or rename it before writing again."
        )

    OUTPUT_DIR.mkdir(parents=True)
    (OUTPUT_DIR / "provenance").mkdir()

    try:
        for relative_path, item in output_files.items():
            path = OUTPUT_DIR / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)

            if item["type"] == "tsv":
                with path.open(
                    "w",
                    encoding="utf-8-sig",
                    newline="",
                ) as file:
                    writer = csv.DictWriter(
                        file,
                        fieldnames=item["fieldnames"],
                        delimiter="\t",
                        extrasaction="raise",
                    )
                    writer.writeheader()
                    writer.writerows(item["rows"])

            elif item["type"] == "json":
                write_json(path, item["data"])

    except Exception:
        # Do not leave a partially generated extension behind.
        import shutil
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Build a separate Lucene assessment extension."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the extension. Without this flag, run a dry run.",
    )
    args = parser.parse_args()

    global SOURCE_METADATA

    print("=== BUILDING LUCENE ASSESSMENT EXTENSION ===")

    SOURCE_METADATA = load_source_metadata()
    print("PASS: Original BGG source fingerprint verified.")

    existing_ids = load_original_pool_ids()
    print("PASS: All nine original assessment pools loaded.")

    reports = load_lucene_reports()
    print("PASS: All 18 Lucene reports validated.")

    comparisons = compare_system_results(reports)

    print("\n=== LUCENE SYSTEM COMPARISON ===")
    for query_id, _ in FORMAL_QUERIES:
        result = comparisons[query_id]
        print(
            f"{query_id}: "
            f"same_top20={result['same_top20']} "
            f"(same_order={result['same_order']}, "
            f"same_scores={result['same_scores']})"
        )

    new_documents = collect_new_documents(reports, existing_ids)

    required_ids = {
        app_id
        for documents in new_documents.values()
        for app_id in documents
    }

    print("\n=== NEW ASSESSMENT DOCUMENTS ===")
    for query_id, query in FORMAL_QUERIES:
        documents = new_documents.get(query_id, {})

        print(f"\n{query_id} – {query}: {len(documents)} new")

        for app_id, appearances in sorted(documents.items()):
            title = appearances[0]["game_title"]

            ranks = ", ".join(
                f"{item['system']} rank {item['rank']}"
                for item in appearances
            )

            print(f"  {app_id}: {title} ({ranks})")

    source_documents = load_source_documents(
        SOURCE_METADATA["path"],
        required_ids,
    )
    print(
        f"\nPASS: Loaded {len(source_documents)} source records "
        "for the new documents."
    )

    output_files, manifest = prepare_output(
        new_documents,
        source_documents,
        reports,
    )

    print("\n=== EXTENSION SUMMARY ===")
    print("Queries with new documents:", len(manifest["queries"]))
    print(
        "New documents across queries:",
        manifest["total_new_documents_across_queries"],
    )
    print("Output directory:", OUTPUT_DIR)

    if args.write:
        write_output(output_files)
        print("\nPASS: Assessment extension created.")
    else:
        print("\nDRY RUN: No files were written.")
        print("Run with --write to create the extension.")


if __name__ == "__main__":
    main()
