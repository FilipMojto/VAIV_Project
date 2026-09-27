from pathlib import Path
import random
import re
import time
from argparse import ArgumentParser
from playwright.sync_api import sync_playwright
from tqdm import tqdm

from src.properties import safe_interrupt_handler
from src.config import DATA_DIR, HARVEST_FILE_NAME
from src.versioning import SmartVersioner

# --- CONFIGURATION ---
TARGET_GAME_COUNT = 15000
BASE_SEARCH_URL = "https://boardgamegeek.com/browse/boardgame/page"
SEARCH_QUERY = "?sort=numvoters&sortdir=desc"
CDP_URL = "http://localhost:9222"
 
# =============================================================================
# ARGPARSER CONFIG
# =============================================================================

parser = ArgumentParser(
    description="Harvest Board Game IDs from BoardGameGeek browse pages via Playwright CDP."
)
parser.add_argument(
    "--output",
    type=Path,
    default=HARVEST_FILE_NAME,
    help=f"Output file for harvested IDs. Default: {HARVEST_FILE_NAME}",
)
parser.add_argument(
    "--target",
    type=int,
    default=TARGET_GAME_COUNT,
    help="Number of unique Game IDs to collect.",
)
parser.add_argument(
    "--start_page", type=int, default=1, help="Page to start harvesting from."
)
parser.add_argument(
    "--smart_append",
    action="store_true",
    help="Enable smart appending to resume from the last checkpoint.",
)
args = parser.parse_args()


def extract_game_ids(html_content: str) -> list[str]:
    # BGG game URLs look like: href="/boardgame/174430/gloomhaven"
    pattern = r'href=["\']/boardgame/(\d+)/'
    matches = re.findall(pattern, html_content)
    seen = set()
    return [
        game_id for game_id in matches if not (game_id in seen or seen.add(game_id))
    ]


def harvest_game_ids(output_file: Path, target_count=TARGET_GAME_COUNT, start_page=1, smart_append=False):
    collected_ids = {}
    page = start_page
    versioner = SmartVersioner(base_filename=output_file.stem, data_dir=DATA_DIR)

    # --- SMART APPENDING (CHECKPOINTING) ---
    if smart_append:
        tqdm.write("Smart appending enabled. Checking for existing checkpoint files...")
        versioner.append_existing_ids(
            collected_ids, target_count=target_count, delimiter="\t", id_column_index=0
        )

    tqdm.write(f"\n--- STARTING GAME ID COLLECTION VIA CDP (Target: {target_count}) ---")
    tqdm.write(f"Writing to temporary safe file: {versioner.get_temp_file_path()}\n")

    with sync_playwright() as p:
        try:
            tqdm.write(f"Connecting to running Chrome instance at {CDP_URL}...")
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            tqdm.write(
                f"\n[ERROR] Could not connect to Chrome on port 9222!\n"
                f"Make sure Chrome is running with `--remote-debugging-port=9222`.\n"
                f"Details: {e}"
            )
            return

        context = browser.contexts[0]
        browser_page = context.pages[0] if context.pages else context.new_page()

        with safe_interrupt_handler(on_interrupt=versioner.dump_temp_to_final):
            with tqdm(
                total=target_count, initial=len(collected_ids), desc="Harvesting IDs", unit="ID"
            ) as pbar:
                while len(collected_ids) < target_count:
                    url = f"{BASE_SEARCH_URL}/{page}{SEARCH_QUERY}"
                    tqdm.write(f"Fetching search page {page}...")

                    try:
                        browser_page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        time.sleep(1.5)  # Brief wait for DOM rendering

                        # Check if Cloudflare pops up mid-scrape
                        if "Just a moment..." in browser_page.title():
                            tqdm.write(
                                f" -> Cloudflare triggered on page {page}! "
                                f"Please solve it manually in your open Chrome window..."
                            )
                            while "Just a moment..." in browser_page.title():
                                time.sleep(2)
                            tqdm.write(" -> Challenge solved! Resuming harvest...")

                        html_content = browser_page.content()
                        ids_found = extract_game_ids(html_content)

                        if not ids_found:
                            tqdm.write("No more games found. Ending harvest loop.")
                            break

                        initial_count = len(collected_ids)

                        for game_id in ids_found:
                            if game_id not in collected_ids:
                                collected_ids[game_id] = None

                        new_added = len(collected_ids) - initial_count

                        tqdm.write(
                            f"  -> Page {page}: Found {len(ids_found)} IDs ({new_added} new). "
                            f"Total: {len(collected_ids)} / {target_count}"
                        )

                        pbar.update(new_added)

                        # Checkpoint write to temporary file
                        with versioner.write_to_temp() as temp_file:
                            for game_id in collected_ids.keys():
                                temp_file.write(f"{game_id}\n")

                        page += 1

                        # Randomized sleep delay (shorter delay is safe over CDP)
                        sleep_time = random.uniform(2.5, 4.0)
                        time.sleep(sleep_time)

                    except Exception as e:
                        tqdm.write(f"Error occurred on page {page}: {e}")
                        break

        # Save final versioned file on successful completion
        versioner.dump_temp_to_final()


if __name__ == "__main__":
    harvest_game_ids(
        output_file=args.output,
        target_count=args.target,
        start_page=args.start_page,
        smart_append=args.smart_append,
    )