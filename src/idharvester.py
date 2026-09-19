import re
import time
import requests

from src.config import DATA_DIR

# --- CONFIGURATION ---
TARGET_GAME_COUNT = 50  # Set to a small number for testing (e.g., 50), increase later (e.g., 1000)
# OUTPUT_FILE = "app_ids.txt"
OUTPUT_FILE = DATA_DIR / "app_ids.txt"

BASE_SEARCH_URL = "https://store.steampowered.com/search/?filter=topsellers&category1=998"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def extract_app_ids(html_content):
    """Regex pattern to capture app IDs from game links (e.g., href="https://store.steampowered.com/app/1086940/...")"""
    pattern = r'href=["\']https://store\.steampowered\.com/app/(\d+)/'
    matches = re.findall(pattern, html_content)
    # Deduplicate while preserving order
    seen = set()
    return [app_id for app_id in matches if not (app_id in seen or seen.add(app_id))]

def harvest_app_ids():
    collected_ids = set()
    page = 1
    
    print(f"--- STARTING APP ID COLLECTION (Target: {TARGET_GAME_COUNT}) ---")

    while len(collected_ids) < TARGET_GAME_COUNT:
        url = f"{BASE_SEARCH_URL}&page={page}"
        print(f"Fetching search page {page}...")

        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                ids_found = extract_app_ids(response.text)
                
                if not ids_found:
                    print("No more games found or reached the end of search results.")
                    break

                # Add new unique IDs
                initial_count = len(collected_ids)
                collected_ids.update(ids_found)
                new_added = len(collected_ids) - initial_count

                print(f"  -> Page {page}: Found {len(ids_found)} IDs ({new_added} new). Total collected: {len(collected_ids)}")
                
                page += 1
                time.sleep(1) # Polite delay to avoid hammering the server
            else:
                print(f"Failed to load page {page}. Status code: {response.status_code}")
                break

        except Exception as e:
            print(f"Error occurred on page {page}: {e}")
            break

    # Truncate to exact target count if we overshot
    final_ids = list(collected_ids)[:TARGET_GAME_COUNT]

    # Save IDs to file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for app_id in final_ids:
            f.write(f"{app_id}\n")

    print(f"\nSuccessfully saved {len(final_ids)} App IDs to '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    harvest_app_ids()