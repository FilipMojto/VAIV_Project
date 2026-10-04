"""Validate the newest scraped BGG TSV for schema and data integrity.

Run with ``python -m src.testdata`` or pass a specific TSV path.  The default
uses SmartVersioner to select the latest timestamped scraper export.
"""

import argparse
import csv
import logging
import re
from datetime import datetime
from pathlib import Path

from src.config import DATA_DIR
from src.versioning import SmartVersioner


BASE_FILENAME = "bgg_games"
EXTENSION = ".tsv"
LOG_DIRECTORY = DATA_DIR / "logs"
LOG_BASENAME = "testdata"

# Keep in sync with the TSV schema written by scrapehtml.process_games.
EXPECTED_FIELDS = (
    "app_id", "game_title", "release_year", "short_description", "num_of_ratings",
    "num_of_comments", "num_of_players", "playing_time", "age", "weight",
    "alternate_names", "designer", "artist", "publisher", "description",
    "awards_honors", "own", "prev_owned", "wishlist", "for_trade", "want_in_trade",
    "has_parts", "wants_parts", "avg_rating", "comments", "fans", "page_views",
    "overall_rank", "strategy_rank", "party_rank", "family_rank", "all_time_plays",
    "all_time_plays_this_month", "html_file_path", "game_type", "game_category",
    "game_mechanic", "game_family", "reimplements", "reimplemented_by",
    "integrates_with", "contains", "contained_in",
)

NONNEGATIVE_INTEGER_FIELDS = (
    "app_id", "release_year", "num_of_ratings", "num_of_comments", "own", "prev_owned",
    "for_trade", "want_in_trade", "wishlist", "has_parts", "wants_parts", "comments",
    "fans", "page_views", "overall_rank", "strategy_rank", "party_rank", "family_rank",
    "all_time_plays", "all_time_plays_this_month",
)
COUNT_FIELDS = tuple(field for field in NONNEGATIVE_INTEGER_FIELDS if field not in {"app_id", "release_year"})
LIST_FIELDS = (
    "game_type", "game_category", "game_mechanic", "game_family", "reimplements",
    "reimplemented_by", "integrates_with", "contains", "contained_in",
)

EXCEPTION_FIELDS = {
    "num_of_ratings": ""
}

def configure_logging(log_dir=LOG_DIRECTORY, level=logging.INFO):
    """Set up console and timestamped file logging; return logger and log path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    log_path = log_dir / f"{LOG_BASENAME}_{timestamp}.log"
    logger = logging.getLogger("testdata")
    logger.setLevel(level)
    logger.propagate = False
    # Avoid duplicate handlers when main() is called repeatedly in one process.
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger, log_path


def _issue(issues, row_num, field, message):
    issues.append(f"row {row_num} [{field}]: {message}")


def validate_row(row, row_num, issues):
    """Append integrity problems found in one DictReader row."""
    for field in EXPECTED_FIELDS:
        if field not in {"html_file_path"} and not (row.get(field) or "").strip():
            # Many BGG fields are legitimately absent. Identity/title are not.
            if field in {"app_id", "game_title"}:
                _issue(issues, row_num, field, "required value is blank")

    for field in NONNEGATIVE_INTEGER_FIELDS:
        value = (row.get(field) or "").strip()
        if not value:
            continue
        if not re.fullmatch(r"\d+", value):
            _issue(issues, row_num, field, f"expected a non-negative integer, got {value!r}")
            continue
        number = int(value)
        if field == "app_id" and number <= 0:
            _issue(issues, row_num, field, "must be greater than zero")
        if field == "release_year" and not 1800 <= number <= 2100:
            _issue(issues, row_num, field, f"outside plausible board-game year range: {number}")
        if field.endswith("_rank") and number == 0:
            _issue(issues, row_num, field, "rank must be positive when present")

    rating = (row.get("avg_rating") or "").strip()
    if rating:
        try:
            rating_number = float(rating)
            if not 0 <= rating_number <= 10:
                _issue(issues, row_num, "avg_rating", f"must be between 0 and 10, got {rating!r}")
        except ValueError:
            _issue(issues, row_num, "avg_rating", f"expected a number, got {rating!r}")

    weight = (row.get("weight") or "").strip()
    if weight:
        try:
            weight_number = float(weight)
            if not 0 <= weight_number <= 5:
                _issue(issues, row_num, "weight", f"must be between 0 and 5, got {weight!r}")
        except ValueError:
            _issue(issues, row_num, "weight", f"expected a number, got {weight!r}")

    players = (row.get("num_of_players") or "").strip()
    if players:
        match = re.fullmatch(r"(\d+)(?:[–-](\d+))?", players)
        if not match:
            _issue(issues, row_num, "num_of_players", f"expected N or N–M, got {players!r}")
        elif match.group(2) and int(match.group(1)) > int(match.group(2)):
            _issue(issues, row_num, "num_of_players", "minimum players exceeds maximum")

    playing_time = (row.get("playing_time") or "").strip()
    if playing_time:
        match = re.fullmatch(r"(\d+)(?:[–-](\d+))?\s+Min", playing_time)
        if not match:
            _issue(issues, row_num, "playing_time", f"expected N Min or N–M Min, got {playing_time!r}")
        elif match.group(2) and int(match.group(1)) > int(match.group(2)):
            _issue(issues, row_num, "playing_time", "minimum time exceeds maximum")

    age = (row.get("age") or "").strip()
    if age and not re.fullmatch(r"\d+\+", age):
        _issue(issues, row_num, "age", f"expected a non-negative age followed by '+', got {age!r}")

    for field in LIST_FIELDS:
        value = (row.get(field) or "").strip()
        if value:
            # parse_game_html stores these as lists; DictWriter serializes a list
            # into a Python-looking string ("['a', 'b']"). Older exports may
            # instead contain a single plain value, so reject only empty items.
            parts = [part.strip() for part in value.split(",")]
            if any(not part for part in parts):
                _issue(issues, row_num, field, "contains an empty list item")

    monthly = (row.get("all_time_plays_this_month") or "").strip()
    lifetime = (row.get("all_time_plays") or "").strip()
    if monthly.isdigit() and lifetime.isdigit() and int(monthly) > int(lifetime):
        _issue(issues, row_num, "all_time_plays_this_month", "monthly plays exceed lifetime plays")

    if row.get("html_file_path"):
        html_path = Path(row["html_file_path"].strip())
        if not html_path.is_file():
            _issue(issues, row_num, "html_file_path", f"file does not exist: {html_path}")


def validate_file(path: Path):
    issues = []
    seen_ids = set()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as tsv_file:
            reader = csv.DictReader(tsv_file, delimiter="\t")
            headers = reader.fieldnames or []
            if not headers:
                return ["file has no TSV header"], 0
            if len(headers) != len(set(headers)):
                issues.append("header contains duplicate column names")
            missing = [field for field in EXPECTED_FIELDS if field not in headers]
            unexpected = [field for field in headers if field not in EXPECTED_FIELDS]
            if missing:
                issues.append(f"header missing fields: {', '.join(missing)}")
            if unexpected:
                issues.append(f"header has unexpected fields: {', '.join(unexpected)}")

            row_count = 1  # header occupies the first line, even for an empty data file
            for row_count, row in enumerate(reader, start=2):
                if None in row:
                    _issue(issues, row_count, "<row>", "more cells than header columns")
                app_id = (row.get("app_id") or "").strip()
                if app_id:
                    if app_id in seen_ids:
                        _issue(issues, row_count, "app_id", f"duplicate ID {app_id!r}")
                    seen_ids.add(app_id)
                validate_row(row, row_count, issues)
            data_rows = max(0, row_count - 1)
    except (OSError, UnicodeError, csv.Error) as exc:
        return [f"could not read {path}: {exc}"], 0
    return issues, data_rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check integrity of the latest BGG scraper TSV.")
    parser.add_argument("file", nargs="?", type=Path, help="TSV to validate; defaults to latest SmartVersioner export")
    args = parser.parse_args(argv)
    logger, log_path = configure_logging()
    logger.info("Integrity validation started; log file: %s", log_path)

    try:
        if args.file:
            data_file = args.file
        else:
            versioner = SmartVersioner(BASE_FILENAME, data_dir=DATA_DIR, extension=EXTENSION)
            latest = versioner.open_latest_save_file()
            if latest is None:
                logger.error("No versioned %s TSV found in %s", BASE_FILENAME, DATA_DIR)
                return 2
            data_file = Path(latest.name)
            latest.close()

        logger.info("Validating TSV: %s", data_file)
        issues, row_count = validate_file(data_file)
        logger.info("Validated %d rows in %s", row_count, data_file)
        if issues:
            logger.warning("Found %d integrity issue(s)", len(issues))
            for issue in issues:
                logger.warning("%s", issue)
            return 1
        logger.info("No integrity issues found")
        return 0
    except Exception:
        logger.exception("Validation failed unexpectedly")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
