from pathlib import Path

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