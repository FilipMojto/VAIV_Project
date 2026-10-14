from collections import deque
import csv
from pathlib import Path
import random
import time

from tqdm import tqdm

from src.scrapehtml import OUTPUT_TSV, extract_html_metadata, load_page_html
from src.parsing import GROUP_FIELD_MAPPINGS, parsing_mappings
from versioning import SmartVersioner
# Sem importuješ svoju existujúcu parsovaciu logiku (zostáva nezmenená!)
# from parser import parse_game_html

# 1. POČIATOČNÝ SEED (prvých 5-10 známych hier z BGG)
SEED_GAME_IDS = [
    "345013",  # Brass: Birmingham
    "167791",  # Terraforming Mars
    "224517",  # Brass: Lancashire
    "479457",  # Braided Skies
    "404883",  # Lairs
]


def extract_linked_game_ids(html_content: str) -> list[str]:
  """Extrahuje app_id iných hier priamo z HTML obsahu aktuálnej stránky

  (napr. z odporúčaní, súvisiacich hier, rozšírení alebo autorov).
  """
  import re

  # Príklad regexu, ktorý hľadá BGG odkazy na iné hry typu /boardgame/123456/
  found_ids = re.findall(r"/boardgame/(\d+)/", html_content)
  return list(set(found_ids))  # odstránime duplicity


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

    while queue and crawled_count < target_games_count:
        app_id = queue.popleft()

        if app_id in visited:
            continue

        print(
            f"[{crawled_count+1}/{target_games_count}] Sťahujem a crawlujem hru"
            f" ID: {app_id}"
        )

        try:
        # 1. Získanie HTML cez tvoj CDP scraper (uloží sa aj do lokálnej cache)
        #   html_content = cdp_scraper.get_html(app_id)
        #   (Tu dosadíš svoje volanie na sťahovanie HTML)
            html_content = load_page_html(page_id=app_id)

            # SIMULÁCIA pre ukážku: predpokladáme, že html_content máme stiahnutý
            # html_content = load_from_cache_or_cdp(app_id)

            # 2. PARSOVANIE - tu využijeme presne tvoju funkciu!
            # game_data = parse_game_html(app_id, html_content)
            # Extrakcia a uloženie
            if html_content:
                game_data = extract_html_metadata(page_id=app_id, html_content=html_content)
                # game_data = {}
                # game_data["app_id"] = app_id

                # for field_type, parser in parsing_mappings.items():
                #     game_data.update(parser(html_content))

                # game_data = parse_game_html(app_id, html_content)
                # game_data["html_file_path"] = file_path
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
            time.sleep(random.uniform(2.5, 4.0))

        except Exception as e:
            print(f"[ERROR] Zlyhalo spracovanie hry {app_id}: {e}")

    output_temp_file.close()
    scraper_versioner.dump_temp_to_final()
    pbar.close()
    print("[INFO] Crawlovanie úspešne dokončené!")


if __name__ == "__main__":
  run_crawler()