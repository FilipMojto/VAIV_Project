
"""Interactive, keyword-assisted relevance assessment for BGG retrieval experiments."""

import argparse
import csv
import os
import re
import sys
import tempfile
from pathlib import Path


ASSESSMENT_DIR = Path("data/assessment/formal_evaluation")
COMPLETED_DIR = Path("data/assessment/completed")

QUERIES = {
    "Q01": {
        "name": "cooperative disease",
        "filename": "Q01_cooperative_disease.tsv",
        "keywords": [
            "cooperative", "co-op", "team", "together",
            "disease", "diseases", "infection", "infected",
            "infectious", "epidemic", "epidemics", "pandemic",
            "pandemics", "virus", "viral", "plague", "outbreak",
            "pathogen", "pathogens", "contagion", "contagious",
            "bacteria", "bacterial", "illness", "sickness",
            "medical", "medicine", "hospital", "cure", "cures",
            "treatment", "treat", "treating", "immunization",
            "quarantine", "spread", "spreading", "vaccine",
            "vaccination", "health"
        ],
    },
}


YELLOW = "\033[1;33m"
RESET = "\033[0m"


def build_keyword_pattern(keywords):
    alternatives = sorted(
        (re.escape(word) for word in keywords),
        key=len,
        reverse=True,
    )
    return re.compile(
        r"\b(?:" + "|".join(alternatives) + r")\b",
        flags=re.IGNORECASE,
    )


def highlight(text, pattern):
    """Highlight matching words without changing the underlying text."""
    if not text:
        return "(none)"

    if os.environ.get("NO_COLOR"):
        return text

    return pattern.sub(
        lambda match: f"{YELLOW}{match.group(0)}{RESET}",
        text,
    )


def save_rows(path, fieldnames, rows):
    """Atomically save the completed assessment TSV."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8-sig",
        newline="",
        dir=path.parent,
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
        writer = csv.DictWriter(
            temporary,
            fieldnames=fieldnames,
            delimiter="\t",
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)

    try:
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def load_assessment(source_path, completed_path):
    with source_path.open(
        encoding="utf-8-sig", newline=""
    ) as source:
        reader = csv.DictReader(source, delimiter="\t")
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not fieldnames or "assessment_id" not in fieldnames:
        raise ValueError("Assessment TSV has no assessment_id column.")

    if "relevance_grade" not in fieldnames:
        raise ValueError("Assessment TSV has no relevance_grade column.")

    if completed_path.exists():
        with completed_path.open(
            encoding="utf-8-sig", newline=""
        ) as completed:
            reader = csv.DictReader(completed, delimiter="\t")

            if reader.fieldnames != fieldnames:
                raise ValueError(
                    "Completed file has different columns from the original."
                )

            completed_rows = list(reader)

        original_ids = [row["assessment_id"] for row in rows]
        completed_ids = [row["assessment_id"] for row in completed_rows]

        if original_ids != completed_ids:
            raise ValueError(
                "Completed file does not match the original assessment pool."
            )

        rows = completed_rows
    else:
        completed_path.parent.mkdir(parents=True, exist_ok=True)
        save_rows(completed_path, fieldnames, rows)

    grades = {"", "0", "1", "2"}
    for row in rows:
        if row["relevance_grade"] not in grades:
            raise ValueError(
                f"Invalid grade in {row['assessment_id']}: "
                f"{row['relevance_grade']!r}"
            )

    return fieldnames, rows


def display_game(row, pattern, position, total):
    print("\n" + "=" * 78)
    print(f"GAME {position}/{total}")
    print(f"Assessment ID: {row['assessment_id']}")
    print(f"BGG ID: {row['app_id']}")
    print(f"\nTITLE: {highlight(row['game_title'], pattern)}")
    print(f"\nRELEASE YEAR: {row['release_year']}")

    for field, label in (
        ("short_description", "SHORT DESCRIPTION"),
        ("description", "FULL DESCRIPTION"),
        ("game_type", "GAME TYPE"),
        ("game_category", "CATEGORIES"),
        ("game_mechanic", "MECHANICS"),
        ("designer", "DESIGNER"),
        ("publisher", "PUBLISHER"),
    ):
        print(f"\n{label}:")
        print(highlight(row.get(field, ""), pattern))

    print("\n" + "-" * 78)


def main():
    parser = argparse.ArgumentParser(
        description="Interactive keyword-assisted relevance assessment."
    )
    parser.add_argument(
        "--query",
        default="Q01",
        choices=sorted(QUERIES),
        help="Query to assess (default: Q01).",
    )
    args = parser.parse_args()

    query = QUERIES[args.query]
    source_path = ASSESSMENT_DIR / query["filename"]
    completed_path = COMPLETED_DIR / query["filename"]

    if not source_path.exists():
        raise FileNotFoundError(source_path)

    fieldnames, rows = load_assessment(
        source_path, completed_path
    )
    pattern = build_keyword_pattern(query["keywords"])

    pending = sum(
        not row["relevance_grade"].strip() for row in rows
    )

    print("=" * 78)
    print(f"RELEVANCE ASSESSMENT: {args.query} – {query['name']}")
    print(f"Total games: {len(rows)}")
    print(f"Already assessed: {len(rows) - pending}")
    print(f"Remaining: {pending}")
    print("=" * 78)
    print("Highlighted words are suggestions, not automatic relevance decisions.")
    print("Grades: 2 = highly relevant | 1 = partially relevant | 0 = not relevant")
    print("Commands: s = skip | q = save and quit")

    if pending == 0:
        print("\nAll games in this query have already been assessed.")
        return

    while True:
        next_index = next(
            (
                index for index, row in enumerate(rows)
                if not row["relevance_grade"].strip()
            ),
            None,
        )

        if next_index is None:
            break

        row = rows[next_index]
        display_game(row, pattern, next_index + 1, len(rows))

        while True:
            grade = input(
                "Relevance grade [0/1/2, s=skip, q=quit]: "
            ).strip().lower()

            if grade in {"0", "1", "2"}:
                row["relevance_grade"] = grade
                save_rows(completed_path, fieldnames, rows)
                print(f"Saved grade {grade} for {row['assessment_id']}.")
                break

            if grade == "s":
                print("Skipped. This game remains unassessed.")
                break

            if grade == "q":
                print("\nProgress saved.")
                print(f"Completed file: {completed_path}")
                return

            print("Please enter 0, 1, 2, s or q.")

    counts = {
        grade: sum(
            row["relevance_grade"] == grade for row in rows
        )
        for grade in ("0", "1", "2")
    }
    remaining = sum(
        not row["relevance_grade"].strip() for row in rows
    )

    print("\n" + "=" * 78)
    print("QUERY ASSESSMENT SUMMARY")
    print(f"Grade 0 – Not relevant: {counts['0']}")
    print(f"Grade 1 – Partially relevant: {counts['1']}")
    print(f"Grade 2 – Highly relevant: {counts['2']}")
    print(f"Still unassessed: {remaining}")
    print(f"Saved to: {completed_path}")
    print("=" * 78)


if __name__ == "__main__":
    main()
