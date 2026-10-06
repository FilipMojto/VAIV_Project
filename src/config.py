from pathlib import Path

WORKDIR = Path(__file__).parent.parent
DATA_DIR = WORKDIR / "data"
HTML_DIR = DATA_DIR / "bgg_raw_htmls"
# -----------------------------------------------------------------------------
# ID Harvesting
# -----------------------------------------------------------------------------
HARVEST_DIR = DATA_DIR / "game_ids"
HARVEST_FILE_NAME = HARVEST_DIR / "app_ids.txt"
HARVEST_TEMP_FILE = HARVEST_DIR / f"{HARVEST_FILE_NAME.stem}_temp.txt"

# -----------------------------------------------------------------------------
# Scraping
# -----------------------------------------------------------------------------
CDP_URL = "http://localhost:9222"
BGG_GAMES_DIR = DATA_DIR / "bgg_games"

