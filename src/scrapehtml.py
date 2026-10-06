import os
import time
import csv
from pathlib import Path
from argparse import ArgumentParser
from playwright.sync_api import sync_playwright
from tqdm import tqdm

from src.config import BGG_GAMES_DIR, DATA_DIR, HARVEST_FILE_NAME
from src.versioning import SmartVersioner
from src.config import CDP_URL
from src.parsing import (
    GROUP_FIELD_MAPPINGS,
    ParserGroup,
    parse_descriptions,
    parse_game_credits,
    parse_game_metrics,
)
from src.parsing import parse_game_ranks, parse_general_fields, parse_general_stats
from src.parsing import (
    parse_player_plays_stats,
    parse_player_stats,
    parse_ratings_and_awards,
)
from src.parsing import parse_relationship_fields
from src.parsing import parsing_mappings
from src.utils import load_html_file

# --- CONFIGURATION ---
OUTPUT_DIR = DATA_DIR / "bgg_raw_htmls"
OUTPUT_TSV = BGG_GAMES_DIR / "bgg_games.tsv"

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
parser.add_argument(
    "--reparse_fields",
    action="store_true",
    help="Reparse every specified field and apply its every transformation(s) from cached HTML.",
)

args = parser.parse_args()


def zero_as_none(value: str) -> str:
    """Convert a string representing a number to None if it is zero or empty."""
    if not value or value == "0":
        return None
    return value


def parse_game_html(app_id: str, html_content: str) -> dict:
    """Extracts game metadata using Regular Expressions from rendered BGG HTML."""
    game_data = {"app_id": app_id}

    for group_name, parser in parsing_mappings.items():
        try:
            # Call the parser function directly
            parsed_dict = parser(html_content)

            # Ensure the parser returned a valid dictionary before updating
            if isinstance(parsed_dict, dict):
                game_data.update(parsed_dict)
            else:
                print(
                    f"[WARNING] Parser '{group_name}' for game {app_id} did not return a dict."
                )

        except Exception as e:
            # Log the specific parser failure without halting the extraction for this game
            print(
                f"[ERROR] Parsing failed for group '{group_name}' on game {app_id}: {e}"
            )

    # --- general fields ---
    game_data.update(parse_general_fields(html_content))

    # --- descriptions ---
    game_data.update(parse_descriptions(html_content))

    # --- game_metrics ---
    game_data.update(parse_game_metrics(html_content))
    # --- Average Rating & Awards ---
    game_data.update(parse_ratings_and_awards(html_content))

    # --- playing_time ---
    game_data.update(parse_player_plays_stats(html_content))

    # --- general_stats ---
    game_data.update(parse_general_stats(html_content))

    # --- game_credits ---
    game_data.update(parse_game_credits(html_content))

    # --- player_stats ---
    game_data.update(parse_player_stats(html_content))

    # --- game ranks ---
    game_data.update(parse_game_ranks(html_content))

    # --- Play Statistics ---
    game_data.update(parse_player_plays_stats(html_content))

    # --- relationship fields ---
    game_data.update(parse_relationship_fields(html_content=html_content))

    return game_data


fields_to_reparse: list[ParserGroup] = [
    # ParserGroup.GENERAL_FIELDS,
    # ParserGroup.GAME_CLASSIFICATION
    ParserGroup.GAME_METRICS
    # ParserGroup.GAME_RANKS
]


def process_games(
    input_file: Path,
    smart_append: bool = False,
    reparse_fields: bool = False,
):
    # Flatten all lists into a single 1D list of headers
    headers = ["app_id"] + [
        field for fields in GROUP_FIELD_MAPPINGS.values() for field in fields
    ]

    harvest_versioner = SmartVersioner(
        base_filename=input_file.stem, data_dir=input_file.parent
    )
    scraper_versioner = SmartVersioner(
        base_filename=OUTPUT_TSV.stem,
        data_dir=OUTPUT_TSV.parent,
        extension=OUTPUT_TSV.suffix,
    )

    # Načítanie zoznamu app_id z input TSV
    app_ids = []
    with harvest_versioner.open_latest_save_file() as f:
        reader = csv.DictReader(
            f,
            delimiter="\t",
            fieldnames=["app_id"],  # <--- Force the header name
            quoting=csv.QUOTE_NONE,
            escapechar="\\",
        )
        for row in reader:
            # Now row will correctly look like: {'app_id': '479457'}
            app_ids.append(row["app_id"])

    # now we run transformations on the existing scraped data if reparse_fields is True
    if reparse_fields:
        print("Reparsing fields...")

        with scraper_versioner.open_latest_save_file() as f:
            reader = csv.DictReader(f, delimiter="\t")
            existing_data = list(reader)

        for row in tqdm(
            existing_data, desc="Reparsing games", total=len(existing_data)
        ):
            app_id = row["app_id"]

            try:
                html_content = load_html_file(app_id)
            except FileNotFoundError as e:
                print(f"[WARNING] Skipping reparse for app_id {app_id}: {e}")
                continue

            # Iterate over each requested parser group and execute its function
            for group in fields_to_reparse:
                parser_func = parsing_mappings.get(group)
                if parser_func:
                    try:
                        new_fields = parser_func(html_content)
                        if isinstance(new_fields, dict):
                            row.update(new_fields)
                    except Exception as e:
                        print(
                            f"[ERROR] Failed parsing {group.value} for app_id {app_id}: {e}"
                        )

        # Save updated dataset back via versioner/DictWriter
        fieldnames = reader.fieldnames or list(existing_data[0].keys())
        for row in existing_data:
            # Remove any stray 'None' key caused by extra tabs in TSV lines
            row.pop(None, None)

            # Ensure any newly parsed fields are added to the TSV header list
            for key in row.keys():
                if key and key not in fieldnames:
                    fieldnames.append(key)
        # 2. Save back safely
        with scraper_versioner.write_to_temp() as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
                delimiter="\t",
                quoting=csv.QUOTE_NONE,
                escapechar="\\",
                extrasaction="ignore",  # Safely drops any unexpected fields instead of throwing ValueError
            )
            writer.writeheader()
            writer.writerows(existing_data)

        scraper_versioner.dump_temp_to_final()

    # Load existing rows before opening the next versioned output. The scrape
    # loop below always writes to this new snapshot, including when no reparse
    # pass was requested.
    latest_file = scraper_versioner.open_latest_save_file()
    if latest_file:
        with latest_file as f:
            reader = csv.DictReader(f, delimiter="\t")
            existing_rows = list(reader)
    else:
        existing_rows = []

    scraped_ids = {
        (row.get("app_id") or "").strip()
        for row in existing_rows
        if (row.get("app_id") or "").strip()
    }
    pending_app_ids = [app_id for app_id in app_ids if app_id not in scraped_ids]
    already_scraped_count = len(app_ids) - len(pending_app_ids)

    tqdm.write(
        f"--- STARTING BGG SCRAPE & PARSE FOR {len(pending_app_ids)} GAMES "
        f"({already_scraped_count} already scraped) ---"
    )

    output_file = scraper_versioner.write_to_temp(newline="")
    writer = csv.DictWriter(
        output_file,
        fieldnames=headers,
        delimiter="\t",
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in existing_rows:
        row.pop(None, None)
        writer.writerow({field: row.get(field, "") for field in headers})

    # Inštancia Playwright mimo slučky, aby sme nadväzovali spojenie iba raz
    with sync_playwright() as p:
        browser = None
        browser_page = None

        for idx, app_id in tqdm(
            enumerate(pending_app_ids, 1),
            total=len(pending_app_ids),
            desc="Processing Games",
            unit="game",
        ):
            file_path = os.path.join(OUTPUT_DIR, f"{app_id}.html")

            # Skontroluj, či už je HTML lokálne uložené
            if os.path.exists(file_path):
                # Najprv načítame obsah a skontrolujeme ho
                html_content = load_html_file(app_id=app_id)

                # Skontrolujeme, či lokálny súbor nie je zablokovaný Cloudflare
                if (
                    "Attention Required! | Cloudflare" in html_content
                    or "Just a moment..." in html_content
                ):
                    tqdm.write(
                        f"[{idx}/{len(pending_app_ids)}] Local HTML for app_id {app_id} contains Cloudflare block. Forcing re-fetch..."
                    )
                    html_content = (
                        None  # Zahodíme zlý obsah, čím vynútime spustenie 'else' vetvy
                    )
                else:
                    tqdm.write(
                        f"[{idx}/{len(pending_app_ids)}] Loading valid cached HTML for app_id {app_id}..."
                    )
            # else:
            # Ak HTML nemáme (alebo bol vyhodnotený ako Cloudflare blok), stiahneme ho
            if not html_content:
                # Ak HTML nemáme a Playwright ešte nebeží, pripoj sa (Lazy načítanie)
                if browser is None:
                    try:
                        browser = p.chromium.connect_over_cdp(CDP_URL)
                        context = browser.contexts[0]
                        browser_page = (
                            context.pages[0] if context.pages else context.new_page()
                        )
                    except Exception as e:
                        tqdm.write(
                            f"[ERROR] Could not connect to Chrome on {CDP_URL}! Details: {e}"
                        )
                        return

                tqdm.write(
                    f"[{idx}/{len(pending_app_ids)}] Fetching HTML for app_id {app_id} via CDP..."
                )
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
                        browser_page.wait_for_selector("span.game-year", timeout=5000)
                    except Exception:
                        # Ak sa nenájde nadpis (napr. hra nemá zadaný rok), počkáme natvrdo
                        time.sleep(3)

                    time.sleep(
                        1
                    )  # Dodatočná sekunda pre istotu, kým sa dočítajú hodnotenia

                    # Ochrana proti Cloudflare (rovnaká ako pri zbere ID)
                    if "Just a moment..." in browser_page.title():
                        tqdm.write(
                            f" -> Cloudflare triggered on {url}! Please solve manually in Chrome..."
                        )
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
                game_data = {}
                game_data["app_id"] = app_id

                for field_type, parser in parsing_mappings.items():
                    game_data.update(parser(html_content))

                # game_data = parse_game_html(app_id, html_content)
                # game_data["html_file_path"] = file_path
                writer.writerow(game_data)
                tqdm.write(
                    f"  -> Parsed: {game_data.get('game_title', 'Unknown')} | Year: {game_data.get('release_year', 'N/A')} | Rating: {game_data.get('avg_rating', 'N/A')}"
                )

    output_file.close()
    scraper_versioner.dump_temp_to_final()


if __name__ == "__main__":
    process_games(
        args.input,
        smart_append=args.smart_append,
        reparse_fields=args.reparse_fields,
    )
