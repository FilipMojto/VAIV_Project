import random
import re
import time
import requests
from argparse import ArgumentParser
from src.smartappending import append_existing_ids
from src.config import DATA_DIR, HARVEST_FILE_NAME, HARVEST_TEMP_FILE
from src.versioning import SmartVersioner

# --- CONFIGURATION ---
TARGET_GAME_COUNT = 15000  
STEAM_CATEGORY_1 = 998 
BASE_SEARCH_URL = f"https://store.steampowered.com/search/?sort_by=Reviews_DESC&category1={STEAM_CATEGORY_1}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Define our safe file paths
# TEMP_FILE = DATA_DIR / "app_ids_temp.txt"

# =============================================================================
# ARGPARSER CONFIG
# =============================================================================

parser = ArgumentParser(description="Harvest Steam App IDs from the Steam Store search pages.")
parser.add_argument("--target", type=int, default=TARGET_GAME_COUNT, help="Number of unique App IDs to collect.")
parser.add_argument("--start_page", type=int, default=1, help="Page to start harvesting from.")
parser.add_argument("--smart_append", action="store_true", help="Enable smart appending to resume from the last checkpoint.")
args = parser.parse_args()

def extract_app_ids(html_content):
    pattern = r'href=["\']https://store\.steampowered\.com/app/(\d+)/'
    matches = re.findall(pattern, html_content)
    seen = set()
    return [app_id for app_id in matches if not (app_id in seen or seen.add(app_id))]

# def get_latest_save_file():
#     """Finds the most recent timestamped app_ids_*.txt file in DATA_DIR."""
#     # glob finds all files matching the pattern, and sorted() puts the newest timestamp last
#     files = list(DATA_DIR.glob("app_ids_*.txt"))
#     if not files:
#         return None
#     return sorted(files)[-1]

def harvest_app_ids(target_count=TARGET_GAME_COUNT, start_page=1, smart_append=False):
    # Using a dictionary to preserve the exact ranking order of the games
    collected_ids = {}
    page = start_page
    versioner = SmartVersioner(base_filename=HARVEST_FILE_NAME, data_dir=DATA_DIR)
    
    # --- SMART APPENDING (CHECKPOINTING) ---
    # latest_file = versioner.open_latest_save_file()
    if smart_append:
        print("Smart appending enabled. Checking for existing checkpoint files...")
        append_existing_ids(versioner, collected_ids, target_count=target_count)
        # latest_file = versioner.open_latest_save_file()
        # # latest_file = versioner.open_latest_save_file()

        # if latest_file:
        #     with latest_file as f:
        #         for line in f:
        #             app_id = line.strip()
        #             if app_id:
        #                 collected_ids[app_id] = None  # Dict keys act as an ordered set
        #     print(f"Loaded {len(collected_ids)} existing IDs into memory.")

        #     if len(collected_ids) >= target_count:
        #         print("Target already reached in the checkpoint file! Exiting.")
        #         return
    
    # if latest_file:
    #     print(f"--- CHECKPOINT FOUND: {latest_file.name} ---")
    #     with open(latest_file, "r", encoding="utf-8") as f:
    #         for line in f:
    #             app_id = line.strip()
    #             if app_id:
    #                 collected_ids[app_id] = None  # Dict keys act as an ordered set
    #     print(f"Loaded {len(collected_ids)} existing IDs into memory.")
        
    #     if len(collected_ids) >= target_count:
    #         print("Target already reached in the checkpoint file! Exiting.")
    #         return

    print(f"\n--- STARTING APP ID COLLECTION (Target: {target_count}) ---")
    print(f"Writing to temporary safe file: {HARVEST_TEMP_FILE.name}")

    while len(collected_ids) < target_count:
        url = f"{BASE_SEARCH_URL}&page={page}"
        print(f"Fetching search page {page}...")

        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                ids_found = extract_app_ids(response.text)
                
                if not ids_found:
                    print("No more games found. Steam may cut off search results at this page limit.")
                    break

                initial_count = len(collected_ids)
                
                # Add new IDs to our ordered dictionary
                for app_id in ids_found:
                    if app_id not in collected_ids:
                        collected_ids[app_id] = None
                        
                new_added = len(collected_ids) - initial_count

                print(f"  -> Page {page}: Found {len(ids_found)} IDs ({new_added} new). Total: {len(collected_ids)} / {target_count}")
                
                # ATOMIC WRITE: Safely overwrite the temp file with the ordered list
                # with open(TEMP_FILE, "w", encoding="utf-8") as f:
                #     for app_id in list(collected_ids.keys())[:target_count]:
                #         f.write(f"{app_id}\n")
                versioner.write_to_temp(list(collected_ids.keys())[:target_count])
                page += 1
                
                # RANDOMIZED HUMAN-LIKE DELAY
                sleep_time = random.uniform(2.5, 4.5)
                time.sleep(sleep_time)

            elif response.status_code == 429:
                print("  -> ERROR 429: Rate limited! Sleeping for 60 seconds...")
                time.sleep(60)
                continue
                
            else:
                print(f"Failed to load page {page}. Status code: {response.status_code}")
                break

        except Exception as e:
            print(f"Error occurred on page {page}: {e}")
            break

    # VERSIONING: Once the loop finishes, rename the temp file with a new timestamp
    versioner.dump_temp_to_final()
    # if TEMP_FILE.exists() and len(collected_ids) > 0:
    #     final_file = versioner.get_next_save_file()
    #     TEMP_FILE.rename(final_file)
    #     print(f"\n--- SUCCESS: Data safely versioned and saved to {final_file.name} ---")

if __name__ == "__main__":
    harvest_app_ids(target_count=args.target, start_page=args.start_page, smart_append=args.smart_append)