import csv
from pathlib import Path
from typing import Iterable, TextIO

from src.config import HTML_DIR


def load_html_file(app_id: str) -> str:
    """Loads the HTML content of a game page from the local HTML_DIR."""
    html_file_path = Path(HTML_DIR) / f"{app_id}.html"
    if not html_file_path.exists():
        raise FileNotFoundError(
            f"HTML file for app_id {app_id} not found at {html_file_path}"
        )

    with open(html_file_path, "r", encoding="utf-8") as file:
        return file.read()


def verify_file_header(
    file: TextIO,
    fields: Iterable[str],
    delim: str = ",",
) -> bool:
    """Verify that a delimited text file contains all required columns."""

    if not file.readable():
        raise ValueError("File is not readable.")

    if not file.seekable():
        raise ValueError("File must support seeking.")

    if not delim:
        raise ValueError("Delimiter cannot be empty.")

    required = set(fields)
    if not required:
        raise ValueError("At least one required field must be specified.")

    try:
        file.seek(0)

        reader = csv.reader(file, delimiter=delim)
        header = next(reader, None)

        if not header or not any(column.strip() for column in header):
            raise ValueError("File is empty or has no valid header.")

        header = [column.strip() for column in header]

        if len(header) != len(set(header)):
            raise ValueError("Duplicate column names found in file header.")

        available = set(header)
        # header = {column.strip() for column in header}
        missing = required - available

        if missing:
            raise ValueError(
                f"Missing required columns: {', '.join(sorted(missing))}"
            )

        return True

    finally:
        file.seek(0)