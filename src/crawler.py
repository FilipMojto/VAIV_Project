from collections import deque
import csv
import json
import os
from pathlib import Path
import random
import re
import time
from argparse import ArgumentParser
from tqdm import tqdm

from src.filecache import FileCache
from src.properties import safe_interrupt_handler
from src.crawling import crawl_page_html
from src.config import BGG_GAMES_DIR, DATA_DIR, OUTPUT_FILE, OUTPUT_TSV

# from src.scrapehtml import OUTPUT_TSV, load_page_html
from src.parsing import GROUP_FIELD_MAPPINGS, ParserGroup, parse_html_metadata
from src.versioning import SmartVersioner

# Sem importuješ svoju existujúcu parsovaciu logiku (zostáva nezmenená!)
# from parser import parse_game_html

# # --- CONFIGURATION ---
# OUTPUT_DIR = DATA_DIR / "bgg_raw_htmls"
# OUTPUT_TSV = BGG_GAMES_DIR / "bgg_games.tsv"

# os.makedirs(BGG_GAMES_DIR, exist_ok=True)
# os.makedirs(OUTPUT_DIR, exist_ok=True)


# 1. POČIATOČNÝ SEED (prvých 5-10 známych hier z BGG)
SEED_GAME_IDS = [
    "13",  # Catan
    "822",  # Carcassonne
    "30549",  # Pandemic
    "266192",  # Wingspan
    "167791",  # Terraforming Mars
]

parser = ArgumentParser(
    description="Crawl and parse BGG game metadata from raw HTML files via Playwright CDP."
)
parser.add_argument(
    "--target", type=int, required=True, help="Intended amount of games to crawl."
)
parser.add_argument(
    "--output_dir",
    type=Path,
    required=False,
    default=BGG_GAMES_DIR,
    help=f"""Specify the directory of the output .tsv file is stored to.
     Defaults to {BGG_GAMES_DIR} """,
)
parser.add_argument(
    "--output",
    type=str,
    required=False,
    default=OUTPUT_FILE,
    help=f"""The TSV filename. Interrupted runs resume from its crawl-state file.
    Choose a different name to start a fresh crawl. Defaults to {OUTPUT_FILE}""",
)

args = parser.parse_args()


def extract_linked_game_ids(html_content: str) -> list[str]:
    """Extrahuje app_id iných hier priamo z HTML obsahu aktuálnej stránky

    (napr. z odporúčaní, súvisiacich hier, rozšírení alebo autorov).
    """
    import re

    # Príklad regexu, ktorý hľadá BGG odkazy na iné hry typu /boardgame/123456/
    found_ids = re.findall(r"/boardgame/(\d+)/", html_content)
    return list(set(found_ids))  # odstránime duplicity


def extract_linked_game_ids(html_content: str, current_app_id: str) -> list[str]:
    """Extrahuje všetky unikátne app_id iných hier priamo z celého HTML obsahu stránky.

    Je to absolútne robustné, nezáleží na vnorených divoch ani zložitom DOM stromu.
    """
    # Nájde všetky výskyty v štýle /boardgame/123386/ nazov-hry
    found_matches = re.findall(r"/boardgame/(\d+)/", html_content)

    # Odstránime duplicity a takisto vynecháme ID aktuálnej stránky, aby sa crawler netočil v kruhu
    unique_ids = [gid for gid in set(found_matches) if gid != str(current_app_id)]

    return unique_ids


def load_crawl_state(state_path: Path) -> dict | None:
    if not state_path.exists():
        return None

    with state_path.open("r", encoding="utf-8") as state_file:
        state = json.load(state_file)

    if (
        not isinstance(state, dict)
        or state.get("version") != 1
        or not isinstance(state.get("queue"), list)
        or not all(isinstance(app_id, str) for app_id in state["queue"])
        or not isinstance(state.get("visited"), list)
        or not all(isinstance(app_id, str) for app_id in state["visited"])
        or (
            state.get("in_flight") is not None
            and not isinstance(state.get("in_flight"), str)
        )
        or not isinstance(state.get("in_flight_completed", False), bool)
    ):
        raise ValueError(f"Invalid crawl state file: {state_path}")

    return state


def save_crawl_state(
    state_path: Path,
    queue: deque,
    visited: set[str],
    in_flight: str | None = None,
    in_flight_completed: bool = False,
):
    temporary_path = state_path.with_suffix(state_path.suffix + ".tmp")
    state = {
        "version": 1,
        "queue": list(queue),
        "visited": sorted(visited),
        "in_flight": in_flight,
        "in_flight_completed": in_flight_completed,
    }
    with temporary_path.open("w", encoding="utf-8", newline="\n") as state_file:
        json.dump(state, state_file, ensure_ascii=False, indent=2)
        state_file.write("\n")
    temporary_path.replace(state_path)


def run_crawler(
    target_games_count: int,
    output_dir: Path,
    output_file: str,
):
    output_file_path = output_dir / output_file
    state_path = output_dir / f"{output_file_path.stem}_crawl_state.json"
    state = load_crawl_state(state_path)

    if state is None:
        queue = deque(SEED_GAME_IDS)
        visited: set[str] = set()
        crawled_count = 0
        print(f"[INFO] Spúšťam crawler so seedom: {SEED_GAME_IDS}")
    else:
        queue = deque(state["queue"])
        visited = set(state["visited"])
        crawled_count = len(visited)
        print(
            f"[INFO] Obnovujem crawler zo stavu: {len(queue)} hier vo fronte, "
            f"{crawled_count} už spracovaných."
        )

    # target_games_count = 500  # alebo koľko dát potrebuješ pre projekt
    active_app_id = None
    deferred_ids: list[str] = []
    # Flatten all lists into a single 1D list of headers
    headers = ["app_id"] + [
        field for fields in GROUP_FIELD_MAPPINGS.values() for field in fields
    ]
    scraper_versioner = SmartVersioner(
        base_filename=output_file_path.stem,
        data_dir=output_file_path.parent,
        extension=output_file_path.suffix,
    )

    output_temp_file = scraper_versioner.open_temp(newline="")
    writer = csv.DictWriter(
        output_temp_file,
        fieldnames=headers,
        delimiter="\t",
        extrasaction="ignore",
    )
    writer.writeheader()

    latest_file = scraper_versioner.get_latest_file()
    saved_game_ids: set[str] = set()

    if latest_file is not None:
        with latest_file.open("r", encoding="utf-8", newline="") as existing_file:
            first_row = next(csv.reader(existing_file, delimiter="\t"), [])
        latest_file_has_header = "app_id" in first_row

        saved_game_ids = FileCache(
            file_path=latest_file,
            identifier_pos=1,
            delimiter="\t",
            contains_header=latest_file_has_header,
        ).row_ids

        with latest_file.open("r", encoding="utf-8", newline="") as existing_file:
            existing_rows = csv.DictReader(
                existing_file,
                delimiter="\t",
                fieldnames=None if latest_file_has_header else headers,
            )
            writer.writerows(existing_rows)

    existing_game_ids = set(saved_game_ids)

    if state is not None and state.get("in_flight") is not None:
        interrupted_app_id = state["in_flight"]
        if state.get("in_flight_completed"):
            if interrupted_app_id in queue:
                queue.remove(interrupted_app_id)
            visited.add(interrupted_app_id)
            crawled_count = len(visited)
            print(
                f"[INFO] Hra {interrupted_app_id} bola spracovaná pred prerušením; "
                "pokračujem ďalšou hrou."
            )
        elif interrupted_app_id not in queue and interrupted_app_id not in visited:
            queue.appendleft(interrupted_app_id)

    # 2. Inicializácia progress baru
    pbar = tqdm(
        total=target_games_count,
        initial=min(crawled_count, target_games_count),
        desc="Crawlovanie BGG hier",
    )

    def save_progress():
        nonlocal crawled_count
        scraper_versioner.dump_temp_to_final()
        in_flight_completed = active_app_id in visited

        if active_app_id is not None and not in_flight_completed:
            latest_output = scraper_versioner.get_latest_file()
            if latest_output is not None and active_app_id not in existing_game_ids:
                with latest_output.open(
                    "r", encoding="utf-8", newline=""
                ) as latest_file_handle:
                    first_row = next(csv.reader(latest_file_handle, delimiter="\t"), [])
                latest_has_header = "app_id" in first_row
                saved_ids = FileCache(
                    file_path=latest_output,
                    identifier_pos=1,
                    delimiter="\t",
                    contains_header=latest_has_header,
                )
                if active_app_id in saved_ids.row_ids:
                    visited.add(active_app_id)
                    crawled_count = len(visited)
                    in_flight_completed = True

        save_crawl_state(
            state_path,
            queue=queue,
            visited=visited,
            in_flight=active_app_id,
            in_flight_completed=in_flight_completed,
        )
        pbar.close()

    with safe_interrupt_handler(on_interrupt=save_progress):
        while queue and crawled_count < target_games_count:
            app_id = queue.popleft()
            if app_id in visited:
                continue
            active_app_id = app_id

            tqdm.write(
                f"[{crawled_count+1}/{target_games_count}] Sťahujem a crawlujem hru"
                f" ID: {app_id}"
            )

            try:
                # 1. Získanie HTML cez tvoj CDP scraper (uloží sa aj do lokálnej cache)
                #   html_content = cdp_scraper.get_html(app_id)
                #   (Tu dosadíš svoje volanie na sťahovanie HTML)
                html_content = crawl_page_html(page_id=app_id, log_func=tqdm.write)
                if not html_content:
                    raise RuntimeError(f"No HTML content returned for game {app_id}")

                ids = extract_linked_game_ids(
                    html_content=html_content, current_app_id=app_id
                )

                for id in ids:
                    if id not in visited and id not in queue:
                        tqdm.write(f"Found new game id {id}! Appending to queue...")
                        queue.append(id)
                    else:
                        tqdm.write(
                            f"Game id {id} already visited or in queue! Skipping..."
                        )

                # SIMULÁCIA pre ukážku: predpokladáme, že html_content máme stiahnutý
                # html_content = load_from_cache_or_cdp(app_id)

                # 2. PARSOVANIE - tu využijeme presne tvoju funkciu!
                # game_data = parse_game_html(app_id, html_content)
                # Extrakcia a uloženie
                if html_content:
                    game_data = parse_html_metadata(
                        page_id=app_id, html_content=html_content
                    )

                    if app_id not in saved_game_ids:
                        writer.writerow(game_data)
                        saved_game_ids.add(app_id)
                    tqdm.write(
                        f"  -> Parsed: {game_data.get('game_title', 'Unknown')} | Year: {game_data.get('release_year', 'N/A')} | Rating: {game_data.get('avg_rating', 'N/A')}"
                    )

                # 3. Uloženie dát do TSV / súboru
                # save_row_to_tsv(game_data)

                # Označíme ako navštívené
                visited.add(app_id)
                crawled_count += 1
                active_app_id = None

                pbar.update(1)

                # 4. NOVÁ ČASŤ PRE CRAWLER: Nájdeme nové hry na stránke a pridáme ich do fronty
                # new_ids = extract_linked_game_ids(html_content)
                # for nid in new_ids:
                #     if nid not in visited and nid not in queue:
                #         queue.append(nid)

                # 5. Povinný rešpekt k serveru (random sleep)
                # sleep_time = random.uniform(2.5, 4.0)
                tqdm.write(f"Current queue size: {len(queue)}")
                time.sleep(random.uniform(2.5, 4.0))

            except Exception as e:
                print(f"[ERROR] Zlyhalo spracovanie hry {app_id}: {e}")
                tqdm.write(f"[ERROR] Zlyhalo spracovanie hry {app_id}: {e}")
                if app_id not in deferred_ids:
                    deferred_ids.append(app_id)
                active_app_id = None
                continue

    output_temp_file.close()
    scraper_versioner.dump_temp_to_final()
    for app_id in deferred_ids:
        if app_id not in queue and app_id not in visited:
            queue.append(app_id)

    if queue:
        save_crawl_state(
            state_path,
            queue=queue,
            visited=visited,
        )
    else:
        state_path.unlink(missing_ok=True)
    pbar.close()
    print("[INFO] Crawlovanie úspešne dokončené!")


if __name__ == "__main__":
    run_crawler(
        target_games_count=args.target,
        output_dir=args.output_dir,
        output_file=args.output,
    )
