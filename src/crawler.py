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

from src.properties import safe_interrupt_handler
from src.crawling import BrowserConnectionError, PageHTMLFetcher
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

CHECKPOINT_INTERVAL = 10


def _upsert_game_row(
    output_rows: list[dict],
    row_indices: dict[str, list[int]],
    game_data: dict,
    headers: list[str],
) -> str:
    app_id = str(game_data["app_id"])
    row = {field: game_data.get(field, "") for field in headers}
    indices = row_indices.get(app_id)

    if indices:
        for index in indices:
            output_rows[index] = row
    else:
        row_indices[app_id] = [len(output_rows)]
        output_rows.append(row)

    return app_id


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

    output_rows: list[dict] = []
    row_indices: dict[str, list[int]] = {}
    latest_file = scraper_versioner.get_latest_match()

    if latest_file is not None:
        with latest_file.open("r", encoding="utf-8", newline="") as existing_file:
            first_row = next(csv.reader(existing_file, delimiter="\t"), [])
        latest_file_has_header = "app_id" in first_row

        with latest_file.open("r", encoding="utf-8", newline="") as existing_file:
            existing_rows = csv.DictReader(
                existing_file,
                delimiter="\t",
                fieldnames=None if latest_file_has_header else headers,
            )
            for existing_row in existing_rows:
                row = {
                    field: existing_row.get(field) or ""
                    for field in headers
                }
                app_id = row["app_id"].strip()
                row_indices.setdefault(app_id, []).append(len(output_rows))
                output_rows.append(row)

    processed_game_ids: set[str] = set()

    def write_temp_snapshot():
        temp_file = scraper_versioner.get_temp_file_path()
        writing_file = temp_file.with_name(f"{temp_file.name}.writing")
        with writing_file.open("w", newline="", encoding="utf-8") as temp_handle:
            writer = csv.DictWriter(
                temp_handle,
                fieldnames=headers,
                delimiter="\t",
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(output_rows)
            temp_handle.flush()
            os.fsync(temp_handle.fileno())
        writing_file.replace(temp_file)

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
        write_temp_snapshot()
        scraper_versioner.dump_temp_to_final()
        in_flight_completed = active_app_id in visited or (
            active_app_id in processed_game_ids
        )
        if in_flight_completed and active_app_id not in visited:
            visited.add(active_app_id)
            crawled_count = len(visited)

        save_crawl_state(
            state_path,
            queue=queue,
            visited=visited,
            in_flight=active_app_id,
            in_flight_completed=in_flight_completed,
        )
        pbar.close()

    with PageHTMLFetcher(log_func=tqdm.write) as page_fetcher:
        with safe_interrupt_handler(on_interrupt=save_progress):
            pending_checkpoint_rows = 0
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
                    html_content = page_fetcher.get_html(page_id=int(app_id))
                    ids = extract_linked_game_ids(
                        html_content=html_content, current_app_id=app_id
                    )

                    for linked_id in ids:
                        if linked_id not in visited and linked_id not in queue:
                            tqdm.write(
                                f"Found new game id {linked_id}! Appending to queue..."
                            )
                            queue.append(linked_id)
                        else:
                            tqdm.write(
                                f"Game id {linked_id} already visited or in queue! "
                                "Skipping..."
                            )

                    game_data = parse_html_metadata(
                        page_id=app_id, html_content=html_content
                    )

                    parsed_app_id = _upsert_game_row(
                        output_rows, row_indices, game_data, headers
                    )
                    processed_game_ids.add(parsed_app_id)
                    pending_checkpoint_rows += 1

                    tqdm.write(
                        f"  -> Parsed: {game_data.get('game_title', 'Unknown')} | "
                        f"Year: {game_data.get('release_year', 'N/A')} | "
                        f"Rating: {game_data.get('avg_rating', 'N/A')}"
                    )

                    visited.add(app_id)
                    crawled_count += 1
                    active_app_id = None
                    pbar.update(1)

                    if pending_checkpoint_rows >= CHECKPOINT_INTERVAL:
                        write_temp_snapshot()
                        save_crawl_state(
                            state_path,
                            queue=queue,
                            visited=visited,
                        )
                        pending_checkpoint_rows = 0

                    tqdm.write(f"Current queue size: {len(queue)}")
                    time.sleep(random.uniform(2.5, 4.0))

                except BrowserConnectionError as e:
                    tqdm.write(f"[ERROR] {e}")
                    queue.appendleft(app_id)
                    active_app_id = None
                    break
                except Exception as e:
                    tqdm.write(
                        f"[ERROR] Zlyhalo spracovanie hry {app_id}: {e}"
                    )
                    if app_id not in deferred_ids:
                        deferred_ids.append(app_id)
                    active_app_id = None
                    continue

    write_temp_snapshot()
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
