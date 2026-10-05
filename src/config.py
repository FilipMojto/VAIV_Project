from pathlib import Path

WORKDIR = Path(__file__).parent.parent
DATA_DIR = WORKDIR / "data"
HTML_DIR = DATA_DIR / "bgg_raw_htmls"
# -----------------------------------------------------------------------------
# ID Harvesting
# -----------------------------------------------------------------------------

HARVEST_FILE_NAME = DATA_DIR / "app_ids.txt"
HARVEST_TEMP_FILE = DATA_DIR / f"{HARVEST_FILE_NAME.stem}_temp.txt"

# -----------------------------------------------------------------------------
# Scraping
# -----------------------------------------------------------------------------
CDP_URL = "http://localhost:9222"

