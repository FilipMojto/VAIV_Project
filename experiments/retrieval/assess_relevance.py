
"""Interactive relevance assessment for the BGG retrieval experiments.

Supports two independent assessment sources:
- tfidf: Original pools generated from the TF-IDF configurations.
- lucene: Additional documents retrieved by the Lucene experiments.

Completed judgments are stored separately for each source.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import tempfile
from pathlib import Path


TFIDF_ASSESSMENT_DIR = Path("data/assessment/formal_evaluation")
TFIDF_COMPLETED_DIR = Path("data/assessment/completed")

LUCENE_ASSESSMENT_DIR = Path("data/assessment/lucene_extension")
LUCENE_COMPLETED_DIR = Path("data/assessment/lucene_extension_completed")


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
            "vaccination", "health",
        ],
    },
    "Q02": {
        "name": "medieval economic strategy",
        "filename": "Q02_medieval_economic_strategy.tsv",
        "keywords": [
            "medieval", "middle ages", "feudal", "feudalism",
            "kingdom", "castle", "economic", "economy",
            "economics", "trade", "trading", "trader",
            "merchant", "merchants", "market", "markets",
            "commerce", "commercial", "production", "produce",
            "resource", "resources", "management", "worker",
            "workers", "placement", "agriculture", "farming",
            "industry", "industries", "coin", "coins", "money",
            "wealth", "income", "investment", "investments",
        ],
    },
    "Q03": {
        "name": "space exploration",
        "filename": "Q03_space_exploration.tsv",
        "keywords": [
            "space", "exploration", "explore", "exploring",
            "explorer", "explorers", "planet", "planets",
            "planetary", "galaxy", "galaxies", "galactic",
            "universe", "cosmos", "cosmic", "star", "stars",
            "stellar", "solar", "system", "systems", "orbit",
            "orbital", "astronaut", "astronauts", "spacecraft",
            "spaceship", "spaceships", "ship", "ships",
            "interstellar", "extraterrestrial", "alien",
            "aliens", "moon", "moons", "asteroid", "asteroids",
            "colony", "colonization", "colonisation",
        ],
    },
    "Q04": {
        "name": "deck building fantasy",
        "filename": "Q04_deck_building_fantasy.tsv",
        "keywords": [
            "deck", "decks", "deckbuilding", "deck-building",
            "deck building", "deckbuilder", "card", "cards",
            "card-based", "fantasy", "fantastical", "magic",
            "magical", "wizard", "wizards", "sorcerer",
            "sorcerers", "witch", "witches", "spell", "spells",
            "dragon", "dragons", "dungeon", "dungeons",
            "mythical", "mythology", "monster", "monsters",
            "adventure", "adventurers", "hero", "heroes",
        ],
    },
    "Q05": {
        "name": "hidden role deduction",
        "filename": "Q05_hidden_role_deduction.tsv",
        "keywords": [
            "hidden", "secret", "secrets", "role", "roles",
            "identity", "identities", "deduction", "deduce",
            "deducing", "deductive", "suspicion", "suspect",
            "suspects", "traitor", "traitors", "betrayal",
            "betray", "bluff", "bluffing", "deception",
            "deceive", "deceiving", "lying", "lie", "lies",
            "clue", "clues", "information", "investigation",
            "investigate", "inference", "infiltrator",
            "infiltrators", "imposter", "impostor",
            "imposters", "impostors", "team", "teams",
        ],
    },
    "Q06": {
        "name": "civilization development",
        "filename": "Q06_civilization_development.tsv",
        "keywords": [
            "civilization", "civilisation", "civilizations",
            "civilisations", "civilizational", "civilisational",
            "development", "develop", "developing", "evolve",
            "evolution", "technology", "technologies",
            "technological", "culture", "cultural", "economy",
            "economic", "empire", "empires", "territory",
            "territories", "expansion", "expand", "expanding",
            "population", "society", "societies", "nation",
            "nations", "history", "historical", "progress",
            "advancement", "advancements", "agriculture",
            "science", "research", "government",
        ],
    },
    "Q07": {
        "name": "train route building",
        "filename": "Q07_train_route_building.tsv",
        "keywords": [
            "train", "trains", "training", "rail", "railway",
            "railways", "railroad", "railroads", "railway",
            "locomotive", "locomotives", "track", "tracks",
            "route", "routes", "routing", "network", "networks",
            "transport", "transportation", "transit", "freight",
            "cargo", "station", "stations", "locomotion",
            "connection", "connections", "connect", "connecting",
            "lines", "line", "express", "steam",
        ],
    },
    "Q08": {
        "name": "negotiation trading",
        "filename": "Q08_negotiation_trading.tsv",
        "keywords": [
            "negotiation", "negotiations", "negotiate",
            "negotiating", "negotiated", "bargain", "bargaining",
            "bargains", "deal", "deals", "deal-making",
            "trading", "trade", "trades", "trader", "traders",
            "exchange", "exchanging", "transaction",
            "transactions", "agreement", "agreements",
            "diplomacy", "diplomatic", "alliance", "alliances",
            "auction", "auctions", "market", "markets",
            "commerce", "merchant", "merchants", "player-to-player",
            "player", "players",
        ],
    },
    "Q09": {
        "name": "solo adventure campaign",
        "filename": "Q09_solo_adventure_campaign.tsv",
        "keywords": [
            "solo", "solitaire", "single-player", "adventure",
            "adventures", "adventurer", "adventurers",
            "campaign", "campaigns", "scenario", "scenarios",
            "narrative", "story", "stories", "storytelling",
            "quest", "quests", "mission", "missions",
            "journey", "journeys", "exploration", "explore",
            "character", "characters", "progression",
            "progress", "chapter", "chapters", "legacy",
            "cooperative", "one-player",
        ],
    },
}


def resolve_paths(query_id: str, source: str) -> tuple[Path, Path]:
    """Return the source and completed assessment paths."""

    query = QUERIES[query_id]

    if source == "tfidf":
        assessment_dir = TFIDF_ASSESSMENT_DIR
        completed_dir = TFIDF_COMPLETED_DIR
    elif source == "lucene":
        assessment_dir = LUCENE_ASSESSMENT_DIR
        completed_dir = LUCENE_COMPLETED_DIR
    else:
        raise ValueError(f"Unknown assessment source: {source}")

    return (
        assessment_dir / query["filename"],
        completed_dir / query["filename"],
    )


def build_keyword_pattern(keywords: list[str]) -> re.Pattern | None:
    """Build a case-insensitive pattern for highlighting query keywords."""

    if not keywords:
        return None

    alternatives = sorted(
        {re.escape(keyword) for keyword in keywords},
        key=len,
        reverse=True,
    )

    expression = r"(?<!\w)(?:" + "|".join(alternatives) + r")(?!\w)"

    return re.compile(expression, re.IGNORECASE)


def highlight(value: str | None, pattern: re.Pattern | None) -> str:
    """Highlight matching terms unless terminal colouring is disabled."""

    if not value:
        return "(none)"

    if pattern is None or os.environ.get("NO_COLOR"):
        return value

    return pattern.sub(
        lambda match: f"\033[93m{match.group(0)}\033[0m",
        value,
    )



def save_rows(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
) -> None:
    """Atomically save assessment rows as a UTF-8-BOM TSV."""

    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            suffix=".tmp",
            prefix=f".{path.name}.",
            dir=path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

            writer = csv.DictWriter(
                temporary_file,
                fieldnames=fieldnames,
                delimiter="\t",
                extrasaction="raise",
            )

            writer.writeheader()
            writer.writerows(rows)

        os.replace(temporary_path, path)

    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()



def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a TSV file and return its header and rows."""

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")

        if reader.fieldnames is None:
            raise ValueError(f"Missing TSV header: {path}")

        fieldnames = reader.fieldnames
        rows = list(reader)

    return fieldnames, rows


def validate_unique_values(
    rows: list[dict[str, str]],
    field: str,
    path: Path,
) -> None:
    """Reject missing or duplicate values in an identifier column."""

    values = [row.get(field, "") for row in rows]

    if any(not value for value in values):
        raise ValueError(f"Empty {field} found in {path}")

    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {field} found in {path}")


def load_assessment(
    source_path: Path,
    completed_path: Path,
) -> tuple[list[str], list[dict[str, str]]]:
    """Load an assessment and validate or initialise its completed copy."""

    if not source_path.is_file():
        raise FileNotFoundError(
            f"Assessment source file does not exist: {source_path}"
        )

    fieldnames, source_rows = read_tsv(source_path)

    required_fields = {"assessment_id", "app_id", "relevance_grade"}
    missing_fields = required_fields - set(fieldnames)

    if missing_fields:
        raise ValueError(
            f"Missing required columns in {source_path}: "
            f"{', '.join(sorted(missing_fields))}"
        )

    validate_unique_values(source_rows, "assessment_id", source_path)
    validate_unique_values(source_rows, "app_id", source_path)

    if completed_path.exists():
        completed_fieldnames, completed_rows = read_tsv(completed_path)

        if completed_fieldnames != fieldnames:
            raise ValueError(
                f"Column mismatch in {completed_path}.\n"
                f"Expected: {fieldnames}\n"
                f"Found:    {completed_fieldnames}"
            )

        validate_unique_values(
            completed_rows,
            "assessment_id",
            completed_path,
        )
        validate_unique_values(
            completed_rows,
            "app_id",
            completed_path,
        )

        source_ids = [row["assessment_id"] for row in source_rows]
        completed_ids = [row["assessment_id"] for row in completed_rows]

        if completed_ids != source_ids:
            raise ValueError(
                f"Assessment IDs or their order have changed in "
                f"{completed_path}"
            )

        # All source fields except relevance_grade must remain unchanged.
        identity_fields = [
            field for field in fieldnames
            if field != "relevance_grade"
        ]

        for index, (source_row, completed_row) in enumerate(
            zip(source_rows, completed_rows),
            start=1,
        ):
            for field in identity_fields:
                if source_row[field] != completed_row[field]:
                    raise ValueError(
                        f"Source metadata changed in {completed_path}, "
                        f"row {index}, field '{field}'."
                    )

        rows = completed_rows

    else:
        rows = [row.copy() for row in source_rows]

        completed_path.parent.mkdir(parents=True, exist_ok=True)
        save_rows(completed_path, fieldnames, rows)

    valid_grades = {"", "0", "1", "2"}

    for row in rows:
        grade = row["relevance_grade"]

        if grade not in valid_grades:
            raise ValueError(
                f"Invalid relevance grade '{grade}' for "
                f"{row['assessment_id']} in {completed_path}"
            )

    return fieldnames, rows


def display_game(
    row: dict[str, str],
    pattern: re.Pattern | None,
    position: int,
    total: int,
) -> None:
    """Display one game and its available metadata."""

    print("\n" + "=" * 78)
    print(f"DOCUMENT {position}/{total}")
    print("=" * 78)

    print(f"Assessment ID: {row.get('assessment_id', '(none)')}")
    print(f"BGG ID:        {row.get('app_id', '(none)')}")
    print(f"Title:         {highlight(row.get('game_title'), pattern)}")
    print(f"Release year:  {row.get('release_year', '(none)')}")

    print("\nShort description:")
    print(highlight(row.get("short_description"), pattern))

    print("\nDescription:")
    print(highlight(row.get("description"), pattern))

    print("\nGame type:")
    print(highlight(row.get("game_type"), pattern))

    print("\nCategories:")
    print(highlight(row.get("game_category"), pattern))

    print("\nMechanics:")
    print(highlight(row.get("game_mechanic"), pattern))

    print("\nDesigner:")
    print(row.get("designer") or "(none)")

    print("\nPublisher:")
    print(row.get("publisher") or "(none)")


def print_summary(rows: list[dict[str, str]]) -> None:
    """Print the current relevance-grade distribution."""

    counts = {"0": 0, "1": 0, "2": 0, "": 0}

    for row in rows:
        counts[row["relevance_grade"]] += 1

    total = len(rows)
    completed = total - counts[""]

    print("\n" + "=" * 50)
    print("ASSESSMENT SUMMARY")
    print("=" * 50)
    print(f"Total documents: {total}")
    print(f"Assessed:        {completed}")
    print(f"Remaining:       {counts['']}")
    print(f"Grade 0:         {counts['0']}")
    print(f"Grade 1:         {counts['1']}")
    print(f"Grade 2:         {counts['2']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive BGG relevance assessment."
    )

    parser.add_argument(
        "--query",
        default="Q01",
        choices=sorted(QUERIES),
        help="Query to assess (default: Q01).",
    )

    parser.add_argument(
        "--source",
        default="tfidf",
        choices=["tfidf", "lucene"],
        help="Assessment pool source (default: tfidf).",
    )

    args = parser.parse_args()

    query_id = args.query
    query = QUERIES[query_id]

    source_path, completed_path = resolve_paths(
        query_id,
        args.source,
    )

    if not source_path.is_file():
        if args.source == "lucene":
            print(
                f"No Lucene extension assessment file exists for "
                f"{query_id} ({query['name']})."
            )
            print(
                "This query had no additional Lucene documents "
                "outside its original TF-IDF assessment pool."
            )
            return

        parser.error(f"Assessment file not found: {source_path}")

    fieldnames, rows = load_assessment(
        source_path,
        completed_path,
    )

    pattern = build_keyword_pattern(query["keywords"])

    pending = [
        index for index, row in enumerate(rows)
        if row["relevance_grade"] == ""
    ]

    print("=" * 78)
    print(f"QUERY: {query_id} — {query['name']}")
    print(f"Source: {args.source}")
    print(f"Assessment file: {source_path}")
    print(f"Completed file:  {completed_path}")
    print("=" * 78)

    print("\nRelevance grades:")
    print("  0 = Not relevant")
    print("  1 = Partially relevant")
    print("  2 = Highly relevant")
    print("\nCommands:")
    print("  s = Skip this document")
    print("  q = Save and quit")

    if not pending:
        print("\nAll documents in this assessment have been graded.")
        print_summary(rows)
        return

    print(f"\nUnassessed documents: {len(pending)}")

    for position, row_index in enumerate(pending, start=1):
        row = rows[row_index]

        display_game(
            row,
            pattern,
            position,
            len(pending),
        )

        while True:
            grade = input(
                "\nRelevance grade [0/1/2, s=skip, q=quit]: "
            ).strip().lower()

            if grade in {"0", "1", "2"}:
                rows[row_index]["relevance_grade"] = grade

                save_rows(completed_path, fieldnames, rows)

                print(f"Saved grade {grade}.")
                break

            if grade == "s":
                print("Skipped.")
                break

            if grade == "q":
                save_rows(completed_path, fieldnames, rows)
                print("\nAssessment saved. Exiting.")
                print_summary(rows)
                return

            print("Invalid input. Enter 0, 1, 2, s, or q.")

    save_rows(completed_path, fieldnames, rows)

    print("\nAssessment completed.")
    print_summary(rows)


if __name__ == "__main__":
    main()
