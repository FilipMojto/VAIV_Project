from collections import deque
import csv
import os
from pathlib import Path
import random
import re
import time
from argparse import ArgumentParser
from tqdm import tqdm

from src.properties import safe_interrupt_handler
from src.crawling import crawl_page_html
from src.config import BGG_GAMES_DIR, DATA_DIR, OUTPUT_TSV
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
    "--output_path",
    type=Path,
    required=False,
    default=OUTPUT_TSV,
    help="Specify path the output .tsv file is stored to.",
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

def run_crawler(target_games_count: int, output_tsv: Path = OUTPUT_TSV):
    queue = deque(SEED_GAME_IDS)
    visited = set()

    # target_games_count = 500  # alebo koľko dát potrebuješ pre projekt
    crawled_count = 0

    print(f"[INFO] Spúšťam crawler so seedom: {SEED_GAME_IDS}")
    # Flatten all lists into a single 1D list of headers
    headers = ["app_id"] + [
        field for fields in GROUP_FIELD_MAPPINGS.values() for field in fields
    ]
    scraper_versioner = SmartVersioner(
        base_filename=output_tsv.stem,
        data_dir=output_tsv.parent,
        extension=output_tsv.suffix,
    )

    output_temp_file = scraper_versioner.open_temp(newline="")
    writer = csv.DictWriter(
        output_temp_file,
        fieldnames=headers,
        delimiter="\t",
        extrasaction="ignore",
    )

    # 2. Inicializácia progress baru
    pbar = tqdm(total=target_games_count, desc="Crawlovanie BGG hier")

    with safe_interrupt_handler(on_interrupt=scraper_versioner.dump_temp_to_final):
        while queue and crawled_count < target_games_count:
            app_id = queue.popleft()

            if app_id in visited:
                continue

            tqdm.write(
                f"[{crawled_count+1}/{target_games_count}] Sťahujem a crawlujem hru"
                f" ID: {app_id}"
            )

            try:
                # 1. Získanie HTML cez tvoj CDP scraper (uloží sa aj do lokálnej cache)
                #   html_content = cdp_scraper.get_html(app_id)
                #   (Tu dosadíš svoje volanie na sťahovanie HTML)
                html_content = crawl_page_html(page_id=app_id, log_func=tqdm.write)
                ids = extract_linked_game_ids(html_content=html_content, current_app_id=app_id)

                for id in ids:
                    if id not in visited and id not in queue:
                        tqdm.write(
                            f"Found new game id {id}! Appending to queue..."
                        )
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

                    writer.writerow(game_data)
                    tqdm.write(
                        f"  -> Parsed: {game_data.get('game_title', 'Unknown')} | Year: {game_data.get('release_year', 'N/A')} | Rating: {game_data.get('avg_rating', 'N/A')}"
                    )

                # 3. Uloženie dát do TSV / súboru
                # save_row_to_tsv(game_data)

                # Označíme ako navštívené
                visited.add(app_id)
                crawled_count += 1

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
                tqdm.write(e)
                continue

    output_temp_file.close()
    scraper_versioner.dump_temp_to_final()
    pbar.close()
    print("[INFO] Crawlovanie úspešne dokončené!")


if __name__ == "__main__":
    run_crawler(target_games_count=args.target, output_tsv=args.output_path)
