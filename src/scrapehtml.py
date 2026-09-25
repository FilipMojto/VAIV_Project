# from argparse import ArgumentParser
# import os
# from pathlib import Path
# import re
# import time
# import requests
# import csv
# from tqdm import tqdm

# from src.properties import safe_interrupt_handler
# from src.config import DATA_DIR, HARVEST_FILE_NAME
# from src.versioning import SmartVersioner

# # --- CONFIGURATION ---
# OUTPUT_DIR = DATA_DIR / "raw_htmls"
# OUTPUT_TSV = DATA_DIR / "steam_games.tsv"

# # Create a directory to store the raw HTML files locally
# os.makedirs(OUTPUT_DIR, exist_ok=True)

# # Cookies to bypass Steam's age-gate for mature games
# COOKIES = {
#     "birthtime": "283993201",
#     "lastagecheckage": "1-0-1979",
#     "wants_mature_content": "1",
# }

# # Force English language to ensure our Regex matches consistently
# HEADERS = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
#     "Accept-Language": "en-US,en;q=0.9",
# }

# parser = ArgumentParser(
#     description="Scrape and parse Steam game metadata from raw HTML files."
# )
# parser.add_argument(
#     "--input",
#     type=Path,
#     default=HARVEST_FILE_NAME,
#     help=f"Path to the input file containing app IDs. Default: {HARVEST_FILE_NAME}",
# )
# parser.add_argument(
#     "--smart_append",
#     action="store_true",
#     help="Enable smart appending to resume from the last checkpoint.",
# )
# args = parser.parse_args()


# def clean_html_text(text):
#     """Removes HTML tags and normalizes whitespace."""
#     if not text:
#         return ""
#     text = re.sub(r"<[^>]+>", "", text)
#     return re.sub(r"\s+", " ", text).strip()


# def parse_game_html(app_id, html_content):
#     """Extracts game metadata using Regular Expressions."""
#     game_data = {"app_id": app_id}

#     # 1. Title
#     title_match = re.search(
#         r'<div class="apphub_AppName"[^>]*>(.*?)</div>', html_content
#     )
#     game_data["game_title"] = (
#         clean_html_text(title_match.group(1)) if title_match else ""
#     )

#     # 2. Developer & Publisher
#     dev_match = re.search(r"Developer:.*?<a[^>]*>(.*?)</a>", html_content, re.DOTALL)
#     game_data["developer"] = clean_html_text(dev_match.group(1)) if dev_match else ""

#     pub_match = re.search(r"Publisher:.*?<a[^>]*>(.*?)</a>", html_content, re.DOTALL)
#     game_data["publisher"] = clean_html_text(pub_match.group(1)) if pub_match else ""

#     # 3. Release Date
#     date_match = re.search(r'<div class="date">(.*?)</div>', html_content)
#     game_data["release_date"] = (
#         clean_html_text(date_match.group(1)) if date_match else ""
#     )

#     # 4. Binary Features (Checking for specific Steam category strings)
#     game_data["is_singleplayer"] = "Single-player" in html_content
#     game_data["is_multiplayer"] = (
#         "Multi-player" in html_content or "Online Co-op" in html_content
#     )

#     # 5. System Requirements (Extracting raw numbers for RAM and Storage)
#     ram_match = re.search(r"Memory:</strong>\s*(\d+)\s*GB", html_content, re.IGNORECASE)
#     game_data["min_ram_gb"] = ram_match.group(1) if ram_match else ""

#     storage_match = re.search(
#         r"Storage:</strong>\s*(\d+)\s*GB", html_content, re.IGNORECASE
#     )
#     game_data["min_storage_gb"] = storage_match.group(1) if storage_match else ""

#     return game_data


# def process_games(input_file: Path, smart_append: bool = False):
#     # Define our dataset schema
#     headers = [
#         "app_id",
#         "game_title",
#         "developer",
#         "publisher",
#         "release_date",
#         "is_singleplayer",
#         "is_multiplayer",
#         "min_ram_gb",
#         "min_storage_gb",
#         "html_file_path",
#     ]

#     harvest_versioner = SmartVersioner(
#         base_filename=input_file.stem, data_dir=input_file.parent
#     )
#     scraper_versioner = SmartVersioner(
#         base_filename=OUTPUT_TSV.stem,
#         data_dir=OUTPUT_TSV.parent,
#         extension=OUTPUT_TSV.suffix,
#     )

#     harvest_file = harvest_versioner.open_latest_save_file()
#     if harvest_file:
#         with harvest_file:
#             app_ids = dict.fromkeys(
#                 line.strip() for line in harvest_file if line.strip()
#             )
#     else:
#         tqdm.write("No harvested app IDs found. Please run the ID harvester first. Exiting.")
#         return

#     # ``newline`` controls physical line endings; the TSV separator belongs to
#     # DictWriter's ``delimiter`` argument below.
#     # Wrap execution in try...except KeyboardInterrupt so Ctrl+C triggers a clean save
#     with safe_interrupt_handler(on_interrupt=scraper_versioner.dump_temp_to_final):
#         with scraper_versioner.write_to_temp(newline="") as tsv_file:
#             writer = csv.DictWriter(tsv_file, fieldnames=headers, delimiter="\t")
#             writer.writeheader()

#             scraped_ids = {}
#             if smart_append:
#                 tqdm.write("Smart appending enabled. Checking for existing scraped data...")
#                 scraper_versioner.append_existing_tsv_rows(writer, scraped_ids)

#             pending_app_ids = [app_id for app_id in app_ids if app_id not in scraped_ids]
#             already_scraped_count = len(app_ids) - len(pending_app_ids)

#             tqdm.write(
#                 f"--- STARTING SCRAPE & PARSE FOR {len(pending_app_ids)} GAMES "
#                 f"({already_scraped_count} already scraped) ---"
#             )

#             # for idx, app_id in enumerate(pending_app_ids, 1):
#             for idx, app_id in tqdm(enumerate(pending_app_ids, 1), total=len(pending_app_ids), desc="Downloading HTMLs", unit="game"):
#                 file_path = os.path.join(OUTPUT_DIR, f"{app_id}.html")
#                 html_content = ""

#                 # Skip download if we already have the raw HTML saved locally
#                 if os.path.exists(file_path):
#                     # print(
#                     #     f"[{idx}/{len(pending_app_ids)}] Loading cached HTML for app_id {app_id}..."
#                     # )
#                     tqdm.write(f"[{idx}/{len(pending_app_ids)}] Loading cached HTML for app_id {app_id}...")
#                     with open(file_path, "r", encoding="utf-8") as f:
#                         html_content = f.read()
#                 else:
#                     tqdm.write(f"[{idx}/{len(pending_app_ids)}] Downloading HTML for app_id {app_id}...")
                    
#                     url = f"https://store.steampowered.com/app/{app_id}/"

#                     try:
#                         response = requests.get(
#                             url, headers=HEADERS, cookies=COOKIES, timeout=10
#                         )
#                         if response.status_code == 200:
#                             html_content = response.text
#                             with open(file_path, "w", encoding="utf-8") as f:
#                                 f.write(html_content)
#                             time.sleep(1.5)  # Polite delay to avoid rate-limiting
#                         else:
#                             tqdm.write(f"  -> Failed. Status: {response.status_code}")
#                             continue
#                     except Exception as e:
#                         tqdm.write(f"  -> Error: {e}")
#                         continue

#                 # Parse the HTML and append to our dataset
#                 if html_content:
#                     game_data = parse_game_html(app_id, html_content)
#                     game_data["html_file_path"] = file_path
#                     writer.writerow(game_data)
#                     tqdm.write(
#                         f"  -> Parsed: {game_data.get('game_title', 'Unknown Title')} | {game_data.get('developer', 'Unknown Dev')}"
#                     )

#         scraper_versioner.dump_temp_to_final()


# if __name__ == "__main__":
#     process_games(args.input, smart_append=args.smart_append)

import os
import re
import time
import csv
from pathlib import Path
from argparse import ArgumentParser
from playwright.sync_api import sync_playwright
from tqdm import tqdm

from src.properties import safe_interrupt_handler
from src.config import DATA_DIR, HARVEST_FILE_NAME
from src.versioning import SmartVersioner

# --- CONFIGURATION ---
OUTPUT_DIR = DATA_DIR / "bgg_raw_htmls"
OUTPUT_TSV = DATA_DIR / "bgg_games.tsv"
CDP_URL = "http://localhost:9222"

os.makedirs(OUTPUT_DIR, exist_ok=True)

parser = ArgumentParser(
    description="Scrape and parse BGG game metadata from raw HTML files via Playwright CDP."
)
parser.add_argument(
    "--input",
    type=Path,
    default=HARVEST_FILE_NAME,
    help=f"Path to the input file containing BGG app IDs. Default: {HARVEST_FILE_NAME}",
)
parser.add_argument(
    "--smart_append",
    action="store_true",
    help="Enable smart appending to resume from the last checkpoint.",
)
args = parser.parse_args()


def clean_html_text(text: str) -> str:
    """Removes HTML tags and normalizes whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_game_html(app_id: str, html_content: str) -> dict:
    """Extracts game metadata using Regular Expressions from rendered BGG HTML."""
    game_data = {"app_id": app_id}

    # ZÁKLADNÉ METADÁTA (Príklady Regexov pre BGG)
    # Názov a rok sa často nachádzajú v title alebo v hlavičke
    title_match = re.search(r'<meta property="og:title" content="(.*?)(?:\s\(\d{4}\))?"', html_content)
    game_data["game_title"] = clean_html_text(title_match.group(1)) if title_match else ""

    year_match = re.search(r'<span[^>]*class="game-year"[^>]*>\((.*?)\)</span>', html_content)
    game_data["release_year"] = clean_html_text(year_match.group(1)) if year_match else ""

    desc_match = re.search(r'<meta name="description" content="(.*?)"', html_content)
    game_data["short_description"] = clean_html_text(desc_match.group(1)) if desc_match else ""

    rating_match = re.search(r'ratingValue":\s*"([\d\.]+)"', html_content)
    game_data["avg_rating"] = rating_match.group(1) if rating_match else ""

    # HRÁČI A ČAS (Príklady pre štruktúrované dáta v BGG)
    players_match = re.search(r'gameplayers[^>]*>.*?(\d+\s*–\s*\d+|\d+)\s*Players', html_content, re.IGNORECASE | re.DOTALL)
    game_data["num_of_players"] = clean_html_text(players_match.group(1)) if players_match else ""

    time_match = re.search(r'gameplaytime[^>]*>.*?(\d+\s*–\s*\d+|\d+)\s*Min', html_content, re.IGNORECASE | re.DOTALL)
    game_data["playing_time"] = clean_html_text(time_match.group(1)) if time_match else ""

    weight_match = re.search(r'Weight:.*?<span[^>]*>(.*?)</span>', html_content, re.IGNORECASE | re.DOTALL)
    game_data["weight"] = clean_html_text(weight_match.group(1)) if weight_match else ""

    # OSTATNÉ POLIA (Placeholder pre tvoje vlastné Regexy podľa HTML)
    game_data["num_of_ratings"] = "" 
    game_data["num_of_comments"] = ""
    game_data["age"] = ""
    game_data["alternate_names"] = ""
    game_data["designer"] = ""
    game_data["artist"] = ""
    game_data["publisher"] = ""
    game_data["description"] = ""
    game_data["awards_honors"] = ""
    game_data["own"] = ""
    game_data["prev_owned"] = ""
    game_data["wishlist"] = ""
    game_data["for_trade"] = ""
    game_data["want_in_trade"] = ""
    game_data["has_parts"] = ""
    game_data["wants_parts"] = ""
    game_data["comments"] = ""
    game_data["fans"] = ""
    game_data["page_views"] = ""
    game_data["overall_rank"] = ""
    game_data["strategy_rank"] = ""
    game_data["all_time_plays"] = ""
    game_data["all_time_plays_this_month"] = ""

    return game_data


def process_games(input_file: Path, smart_append: bool = False):
    # Kompletná schéma datasetu zadefinovaná podľa zadania
    headers = [
        "app_id", "game_title", "release_year", "short_description", "num_of_ratings",
        "num_of_comments", "num_of_players", "playing_time", "age", "weight", 
        "alternate_names", "designer", "artist", "publisher", "description", 
        "awards_honors", "own", "prev_owned", "wishlist", "for_trade", "want_in_trade", 
        "has_parts", "wants_parts", "avg_rating", "comments", "fans", "page_views", 
        "overall_rank", "strategy_rank", "all_time_plays", "all_time_plays_this_month",
        "html_file_path"
    ]

    harvest_versioner = SmartVersioner(base_filename=input_file.stem, data_dir=input_file.parent)
    scraper_versioner = SmartVersioner(base_filename=OUTPUT_TSV.stem, data_dir=OUTPUT_TSV.parent, extension=OUTPUT_TSV.suffix)

    harvest_file = harvest_versioner.open_latest_save_file()
    if harvest_file:
        with harvest_file:
            # Predpokladáme, že BGG ID sú v prvom stĺpci, ak sú tam tabulátory
            app_ids = dict.fromkeys(line.split("\t")[0].strip() for line in harvest_file if line.strip())
    else:
        tqdm.write("No harvested app IDs found. Please run the ID harvester first. Exiting.")
        return

    with safe_interrupt_handler(on_interrupt=scraper_versioner.dump_temp_to_final):
        with scraper_versioner.write_to_temp(newline="") as tsv_file:
            writer = csv.DictWriter(tsv_file, fieldnames=headers, delimiter="\t")
            writer.writeheader()

            scraped_ids = {}
            if smart_append:
                tqdm.write("Smart appending enabled. Checking for existing scraped data...")
                scraper_versioner.append_existing_tsv_rows(writer, scraped_ids, id_column="app_id")

            pending_app_ids = [app_id for app_id in app_ids if app_id not in scraped_ids]
            already_scraped_count = len(app_ids) - len(pending_app_ids)

            tqdm.write(
                f"--- STARTING BGG SCRAPE & PARSE FOR {len(pending_app_ids)} GAMES "
                f"({already_scraped_count} already scraped) ---"
            )

            # Inštancia Playwright mimo slučky, aby sme nadväzovali spojenie iba raz
            with sync_playwright() as p:
                browser = None
                browser_page = None

                for idx, app_id in tqdm(enumerate(pending_app_ids, 1), total=len(pending_app_ids), desc="Processing Games", unit="game"):
                    file_path = os.path.join(OUTPUT_DIR, f"{app_id}.html")
                    html_content = ""

                    # Skontroluj, či už je HTML lokálne uložené
                    if os.path.exists(file_path):
                        tqdm.write(f"[{idx}/{len(pending_app_ids)}] Loading cached HTML for app_id {app_id}...")
                        with open(file_path, "r", encoding="utf-8") as f:
                            html_content = f.read()
                    else:
                        # Ak HTML nemáme a Playwright ešte nebeží, pripoj sa (Lazy načítanie)
                        if browser is None:
                            try:
                                browser = p.chromium.connect_over_cdp(CDP_URL)
                                context = browser.contexts[0]
                                browser_page = context.pages[0] if context.pages else context.new_page()
                            except Exception as e:
                                tqdm.write(f"[ERROR] Could not connect to Chrome on {CDP_URL}! Details: {e}")
                                return

                        tqdm.write(f"[{idx}/{len(pending_app_ids)}] Fetching HTML for app_id {app_id} via CDP...")
                        url = f"https://boardgamegeek.com/boardgame/{app_id}/"

                        try:
                            # Prejdeme na stránku a počkáme na stiahnutie Javascriptových dát
                            # browser_page.goto(url, wait_until="networkidle", timeout=30000)
                            # time.sleep(2)  # Krátky delay pre vyrenderovanie komponentov
                            # OPRAVENÝ KÓD
                            # domcontentloaded načíta štruktúru bez čakania na reklamy a trackery
                            browser_page.goto(url, wait_until="domcontentloaded", timeout=30000)

                            # Ak chceš mať istotu, že sa načítali dáta hry, počkáme, kým sa zjaví hlavný nadpis
                            try:
                                # Čakáme max 5 sekúnd na vyrenderovanie elementu, ktorý obsahuje rok alebo názov
                                browser_page.wait_for_selector('span.game-year', timeout=5000)
                            except Exception:
                                # Ak sa nenájde nadpis (napr. hra nemá zadaný rok), počkáme natvrdo
                                time.sleep(3) 

                            time.sleep(1) # Dodatočná sekunda pre istotu, kým sa dočítajú hodnotenia

                            # Ochrana proti Cloudflare (rovnaká ako pri zbere ID)
                            if "Just a moment..." in browser_page.title():
                                tqdm.write(f" -> Cloudflare triggered on {url}! Please solve manually in Chrome...")
                                while "Just a moment..." in browser_page.title():
                                    time.sleep(2)
                                tqdm.write(" -> Challenge solved! Resuming...")

                            html_content = browser_page.content()
                            
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(html_content)

                            # Náhodný sleep medzi požiadavkami, keď reálne sťahujeme
                            time.sleep(1.5)

                        except Exception as e:
                            tqdm.write(f"  -> Error fetching page: {e}")
                            continue

                    # Extrakcia a uloženie
                    if html_content:
                        game_data = parse_game_html(app_id, html_content)
                        game_data["html_file_path"] = file_path
                        writer.writerow(game_data)
                        tqdm.write(
                            f"  -> Parsed: {game_data.get('game_title', 'Unknown')} | Year: {game_data.get('release_year', 'N/A')} | Rating: {game_data.get('avg_rating', 'N/A')}"
                        )

        scraper_versioner.dump_temp_to_final()


if __name__ == "__main__":
    process_games(args.input, smart_append=args.smart_append)