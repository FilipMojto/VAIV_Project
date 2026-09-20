import os
import re
import time
import requests
import csv

from src.config import DATA_DIR

# --- CONFIGURATION ---
# INPUT_FILE = "app_ids.txt"
INPUT_FILE = DATA_DIR / "app_ids.txt"
OUTPUT_DIR = DATA_DIR / "raw_htmls"
OUTPUT_TSV = DATA_DIR / "steam_games.tsv"

# Create a directory to store the raw HTML files locally
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Cookies to bypass Steam's age-gate for mature games
COOKIES = {
    "birthtime": "283993201",
    "lastagecheckage": "1-0-1979",
    "wants_mature_content": "1"
}

# Force English language to ensure our Regex matches consistently
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9" 
}

def clean_html_text(text):
    """Removes HTML tags and normalizes whitespace."""
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def parse_game_html(app_id, html_content):
    """Extracts game metadata using Regular Expressions."""
    game_data = {"app_id": app_id}
    
    # 1. Title
    title_match = re.search(r'<div class="apphub_AppName"[^>]*>(.*?)</div>', html_content)
    game_data["game_title"] = clean_html_text(title_match.group(1)) if title_match else ""
    
    # 2. Developer & Publisher
    dev_match = re.search(r'Developer:.*?<a[^>]*>(.*?)</a>', html_content, re.DOTALL)
    game_data["developer"] = clean_html_text(dev_match.group(1)) if dev_match else ""
    
    pub_match = re.search(r'Publisher:.*?<a[^>]*>(.*?)</a>', html_content, re.DOTALL)
    game_data["publisher"] = clean_html_text(pub_match.group(1)) if pub_match else ""
    
    # 3. Release Date
    date_match = re.search(r'<div class="date">(.*?)</div>', html_content)
    game_data["release_date"] = clean_html_text(date_match.group(1)) if date_match else ""

    # 4. Binary Features (Checking for specific Steam category strings)
    game_data["is_singleplayer"] = "Single-player" in html_content
    game_data["is_multiplayer"] = "Multi-player" in html_content or "Online Co-op" in html_content

    # 5. System Requirements (Extracting raw numbers for RAM and Storage)
    ram_match = re.search(r'Memory:</strong>\s*(\d+)\s*GB', html_content, re.IGNORECASE)
    game_data["min_ram_gb"] = ram_match.group(1) if ram_match else ""

    storage_match = re.search(r'Storage:</strong>\s*(\d+)\s*GB', html_content, re.IGNORECASE)
    game_data["min_storage_gb"] = storage_match.group(1) if storage_match else ""

    return game_data

def process_games():
    # Define our dataset schema
    headers = ["app_id", "game_title", "developer", "publisher", "release_date", 
               "is_singleplayer", "is_multiplayer", "min_ram_gb", "min_storage_gb"]
    
    file_exists = os.path.isfile(OUTPUT_TSV)
    
    with open(OUTPUT_TSV, "a", newline='', encoding="utf-8") as tsv_file:
        writer = csv.DictWriter(tsv_file, fieldnames=headers, delimiter='\t')
        if not file_exists:
            writer.writeheader()

        with open(INPUT_FILE, "r") as f:
            app_ids = [line.strip() for line in f if line.strip()]

        print(f"--- STARTING SCRAPE & PARSE FOR {len(app_ids)} GAMES ---")

        for idx, app_id in enumerate(app_ids, 1):
            file_path = os.path.join(OUTPUT_DIR, f"{app_id}.html")
            html_content = ""

            # Skip download if we already have the raw HTML saved locally
            if os.path.exists(file_path):
                print(f"[{idx}/{len(app_ids)}] Loading cached HTML for app_id {app_id}...")
                with open(file_path, "r", encoding="utf-8") as f:
                    html_content = f.read()
            else:
                print(f"[{idx}/{len(app_ids)}] Downloading HTML for app_id {app_id}...")
                url = f"https://store.steampowered.com/app/{app_id}/"
                # print(f"[{idx}/{len(app_ids)}] Downloading {url}...")
                try:
                    response = requests.get(url, headers=HEADERS, cookies=COOKIES, timeout=10)
                    if response.status_code == 200:
                        html_content = response.text
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(html_content)
                        time.sleep(1.5) # Polite delay to avoid rate-limiting
                    else:
                        print(f"  -> Failed. Status: {response.status_code}")
                        continue
                except Exception as e:
                    print(f"  -> Error: {e}")
                    continue

            # Parse the HTML and append to our dataset
            if html_content:
                game_data = parse_game_html(app_id, html_content)
                writer.writerow(game_data)
                print(f"  -> Parsed: {game_data.get('game_title', 'Unknown Title')} | {game_data.get('developer', 'Unknown Dev')}")

if __name__ == "__main__":
    process_games()