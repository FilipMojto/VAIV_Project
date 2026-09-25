# # import random
# # import re
# # import time
# # # import requests
# # import cloudscraper  # Replaces requests
# # from argparse import ArgumentParser
# # from tqdm.asyncio import tqdm

# # from src.properties import safe_interrupt_handler
# # from src.config import DATA_DIR, HARVEST_FILE_NAME, HARVEST_TEMP_FILE
# # from src.versioning import SmartVersioner

# # # --- CONFIGURATION ---
# # TARGET_GAME_COUNT = 15000
# # # Base URL for Browse page; using numvoters to sort by most popular/rated
# # BASE_SEARCH_URL = "https://boardgamegeek.com/browse/boardgame/page"
# # SEARCH_QUERY = "?sort=numvoters&sortdir=desc"

# # HEADERS = {
# #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
# #     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
# #     "Accept-Language": "en-US,en;q=0.5",
# # }

# # # =============================================================================
# # # ARGPARSER CONFIG
# # # =============================================================================

# # parser = ArgumentParser(
# #     description="Harvest Board Game IDs from BoardGameGeek browse pages."
# # )
# # parser.add_argument(
# #     "--target",
# #     type=int,
# #     default=TARGET_GAME_COUNT,
# #     help="Number of unique Game IDs to collect.",
# # )
# # parser.add_argument(
# #     "--start_page", type=int, default=1, help="Page to start harvesting from."
# # )
# # parser.add_argument(
# #     "--smart_append",
# #     action="store_true",
# #     help="Enable smart appending to resume from the last checkpoint.",
# # )
# # args = parser.parse_args()


# # def extract_game_ids(html_content):
# #     # BGG game URLs look like: href="/boardgame/174430/gloomhaven"
# #     pattern = r'href=["\']/boardgame/(\d+)/'
# #     matches = re.findall(pattern, html_content)
# #     seen = set()
# #     return [
# #         game_id for game_id in matches if not (game_id in seen or seen.add(game_id))
# #     ]



# # def harvest_game_ids(target_count=TARGET_GAME_COUNT, start_page=1, smart_append=False):
# #     collected_ids = {}
# #     page = start_page
# #     versioner = SmartVersioner(base_filename=HARVEST_FILE_NAME.stem, data_dir=DATA_DIR)
    
# #     # Initialize Cloudscraper with a Chrome fingerprint
# #     scraper = cloudscraper.create_scraper(browser={
# #         'browser': 'chrome',
# #         'platform': 'windows',
# #         'desktop': True
# #     })
    
# #     # --- SMART APPENDING (CHECKPOINTING) ---
# #     if smart_append:
# #         tqdm.write("Smart appending enabled. Checking for existing checkpoint files...")
# #         versioner.append_existing_ids(collected_ids, target_count=target_count,
# #                                       delimiter="\t", id_column_index=0)

# #     tqdm.write(f"\n--- STARTING GAME ID COLLECTION (Target: {target_count}) ---")
# #     tqdm.write(f"Writing to temporary safe file: {HARVEST_TEMP_FILE.name}")

# #     with safe_interrupt_handler(on_interrupt=versioner.dump_temp_to_final):
# #         with tqdm(total=target_count, initial=len(collected_ids), desc="Harvesting IDs", unit="ID") as pbar:
# #             while len(collected_ids) < target_count:
# #                 url = f"{BASE_SEARCH_URL}/{page}{SEARCH_QUERY}"
# #                 tqdm.write(f"Fetching search page {page}...")

# #                 try:
# #                     # Use scraper.get instead of requests.get
# #                     response = scraper.get(url, headers=HEADERS, timeout=15)
                    
# #                     if response.status_code == 200:
# #                         ids_found = extract_game_ids(response.text)
                        
# #                         if not ids_found:
# #                             tqdm.write("No more games found. BGG may cut off search results at this page limit.")
# #                             break

# #                         initial_count = len(collected_ids)

# #                         # Add new IDs to our ordered dictionary
# #                         for game_id in ids_found:
# #                             if game_id not in collected_ids:
# #                                 collected_ids[game_id] = None

# #                         new_added = len(collected_ids) - initial_count

# #                         tqdm.write(
# #                             f"  -> Page {page}: Found {len(ids_found)} IDs ({new_added} new). Total: {len(collected_ids)} / {target_count}"
# #                         )

# #                         # update progress bar
# #                         pbar.update(new_added)

# #                         with versioner.write_to_temp() as temp_file:
# #                             for game_id in collected_ids.keys():
# #                                 temp_file.write(f"{game_id}\n")

# #                         page += 1

# #                         # RANDOMIZED HUMAN-LIKE DELAY
# #                         # BGG can be strict with basic scraping. Keep this relatively high.
# #                         # sleep_time = random.uniform(3.0, 5.5)
# #                         sleep_time = random.uniform(5.2, 7.0)

# #                         time.sleep(sleep_time)

# #                     elif response.status_code == 429:
# #                         tqdm.write(
# #                             "  -> ERROR 429: Rate limited! Sleeping for 60 seconds..."
# #                         )
# #                         time.sleep(60)
# #                         continue

# #                     else:
# #                         tqdm.write(
# #                             f"Failed to load page {page}. Status code: {response.status_code}"
# #                         )
# #                         break

# #                 except Exception as e:
# #                     tqdm.write(f"Error occurred on page {page}: {e}")
# #                     break

# #             # VERSIONING: Once the loop finishes, rename the temp file with a new timestamp
# #             versioner.dump_temp_to_final()


# # if __name__ == "__main__":
# #     harvest_game_ids(
# #         target_count=args.target,
# #         start_page=args.start_page,
# #         smart_append=args.smart_append,
# #     )
# import random
# import re
# import time
# import requests
# from argparse import ArgumentParser
# from tqdm.asyncio import tqdm

# from src.properties import safe_interrupt_handler
# from src.config import DATA_DIR, HARVEST_FILE_NAME, HARVEST_TEMP_FILE
# from src.versioning import SmartVersioner

# # --- CONFIGURATION ---
# TARGET_GAME_COUNT = 15000
# # Base URL for Browse page; using numvoters to sort by most popular/rated
# BASE_SEARCH_URL = "https://boardgamegeek.com/browse/boardgame/page"
# SEARCH_QUERY = "?sort=numvoters&sortdir=desc"

# # Paste your exact values from your real browser here
# # CF_CLEARANCE = "WgNyjkk7vH2r43gyn0WWqoT3kzkXb8wt98QSCo5lVoA-1790355366-1.2.1.1-LEhNngjQNRdcZT0q_RaQQNKCVkG8ulrKLIaWAN30kTZEDfxRtsLP62_1habl9HK7KbpcYoc8HAfsCBfx9WeO8JLMWxI2IByYvAc7r.Xc52t8e7fKSx9xrMbgXKeLdlACcmKfPHfTx7owvjtkiUEsrRplpAVsgYtCQUUTpr0Y9eTBnooginCV2osbe6cPq8OTy80hRzKUwQa3nF0SBB9sWwpcGERjFkhwsutyJ3rXucTgHl.9eR_QVPUkAWCFxyvTuY.LF3VNNBnBed0ZL.WMM191BqyeFZyVabe1TtE.8_lrIEIN5qc7_SBT40fVf132jVNiBloprx2MSs24ew54znVZzySgR2cw4DFQ_y4Xt3BtyrPs1yGRZLMZpvcVvPvLL2ufoFbHSbm_5bTjBzagGLaFSxqUkgwBISFT9Y0vWxjbev1u0Xp1Z8ehoEVjnhUIwsv6SESf8mwlwwBMkNnAhYUA5lmlPPWa.e1WIqWy2XG._lPxPOGB_1nyLcQIZHEV"
# # CF_CLEARANCE = "CCX0BJEFUwY3XvcjCFSaen74yMpu0Kk5WvOzt3eoD5k-1790374100-1.2.1.1-TBkLSFOi2RKeH4ulBR94gzCM26fFlJp4_fphWAy7_OqVgyhKPFy6AYPrEJ9YljwFC2a63SJLRVhG9EvY1n7bxlSEhI2YqnxQnyVc0TVfvm6Tevh7AipeCzNvPTDNbbAo0utmFNUityDAcroscB7BkR9j5n_LaKAzKZ_MP1tqL8ExtjWvAdQPq7Rben17y74MkZC25yv.hBNow8bwfVlMj8yCzJBdVwSjxb2KnNBbB7hfhYz72sKqT5IeAFbLURUUt7DnRlB4kz929YLxKTB0BkS39SPUTkw1kZdKFYllCfdcJ.oMGoRquLwQDFlc31M0F_RJkqb8UMzzQ82IFqaDDd5xxooSDV45.e2ONs1.fR1vxnoQArp5dIPTJUoeNXkTtW_zoeU6.cdNtkKjj5oVMYsfHdXBjNthNMwVJCAwUf0H2yuvAwm4OTKrw1C0ID8E46lt5A3D0CmWaVKXFDb_aH_mm.Pzd9eHcuL.yHwqgyZua6KWrg8G1dUIPY9TeK7OzK5YPs107TpkL6gtNA7KceyTiUk.AYv1OiqFX3oyexsgOvAX_QDJFBaX32Z2lU.o"
# CF_CLEARANCE = "5UEw8Zk_KKgHiFJvdU03vleRNsATlwmVl.0tjBxC0us-1790374180-1.2.1.1-bvKBIws.8M_CPGa_E8t4fwH4k.fy8EuvhEAMIAodFITwVsGgttQCzAVBIZXAGLUdt1DRVs7xtMrGvMh7t2VRt5ssMbWbP.G_cmdzkCDj7ag.4MNPKEd6sYNZfAaJzdKZxhJElFzZj.1vwEOlIqnseb9xoTZ2sj.2sQL8E.Ciu6JsJPXpLAWocLM..HjjSKlikS7f0lDlCxV4HAa87rVaB5jodYGpRxx1bXT.lKA9CLJ7yQH_MDFC4KNfvP3I5suZrJx0lG3.i61c0lsFtlu0Bg6ionJghqQjvjBxlu4tfnTKgrFiG55MRr9.0jIbQuETkLXIhWTZ5XmNyzjgtjohkzzXa0lr1IQvkD7B8EiWENQVcCuHr_dedLiOguc1tZFIqZw_6vxi89Oiciz1f2HB3s8UA5kE7oTtGkkfA3eWbr2C_aKlcxSnuPid3abEXvXBeu1IkwC3g5TxtalfqiSvqcno5JllOyUY._Xl9V3UXr_xQMyTF.nSlRZjJaIM_QNDnPQcxvsF1sxlBPaEXaNFIKNVMKzKep.AuwW5tOE0m.Ic5JQt2dYqzElXKSImireA"
# USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"

# # =============================================================================
# # ARGPARSER CONFIG
# # =============================================================================

# parser = ArgumentParser(
#     description="Harvest Board Game IDs from BoardGameGeek browse pages."
# )
# parser.add_argument(
#     "--target",
#     type=int,
#     default=TARGET_GAME_COUNT,
#     help="Number of unique Game IDs to collect.",
# )
# parser.add_argument(
#     "--start_page", type=int, default=1, help="Page to start harvesting from."
# )
# parser.add_argument(
#     "--smart_append",
#     action="store_true",
#     help="Enable smart appending to resume from the last checkpoint.",
# )
# args = parser.parse_args()


# def extract_game_ids(html_content):
#     # BGG game URLs look like: href="/boardgame/174430/gloomhaven"
#     pattern = r'href=["\']/boardgame/(\d+)/'
#     matches = re.findall(pattern, html_content)
#     seen = set()
#     return [
#         game_id for game_id in matches if not (game_id in seen or seen.add(game_id))
#     ]


# def harvest_game_ids(target_count=TARGET_GAME_COUNT, start_page=1, smart_append=False):
#     collected_ids = {}
#     page = start_page
#     versioner = SmartVersioner(base_filename=HARVEST_FILE_NAME.stem, data_dir=DATA_DIR)
    
#     # --- Initialize Authenticated Session ---
#     session = requests.Session()
#     session.headers.update({
#         "User-Agent": USER_AGENT,
#         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
#         "Accept-Language": "en-US,en;q=0.9",
#     })
#     session.cookies.set("cf_clearance", CF_CLEARANCE, domain=".boardgamegeek.com")
    
#     # --- SMART APPENDING (CHECKPOINTING) ---
#     if smart_append:
#         tqdm.write("Smart appending enabled. Checking for existing checkpoint files...")
#         versioner.append_existing_ids(collected_ids, target_count=target_count,
#                                       delimiter="\t", id_column_index=0)

#     tqdm.write(f"\n--- STARTING GAME ID COLLECTION (Target: {target_count}) ---")
#     tqdm.write(f"Writing to temporary safe file: {HARVEST_TEMP_FILE.name}")

#     with safe_interrupt_handler(on_interrupt=versioner.dump_temp_to_final):
#         with tqdm(total=target_count, initial=len(collected_ids), desc="Harvesting IDs", unit="ID") as pbar:
#             while len(collected_ids) < target_count:
#                 url = f"{BASE_SEARCH_URL}/{page}{SEARCH_QUERY}"
#                 tqdm.write(f"Fetching search page {page}...")

#                 try:
#                     # Use session.get to utilize the clearance cookie
#                     response = session.get(url, timeout=15)
                    
#                     if response.status_code == 200 and "Just a moment..." not in response.text:
#                         ids_found = extract_game_ids(response.text)
                        
#                         if not ids_found:
#                             tqdm.write("No more games found. BGG may cut off search results at this page limit.")
#                             break

#                         initial_count = len(collected_ids)

#                         # Add new IDs to our ordered dictionary
#                         for game_id in ids_found:
#                             if game_id not in collected_ids:
#                                 collected_ids[game_id] = None

#                         new_added = len(collected_ids) - initial_count

#                         tqdm.write(
#                             f"  -> Page {page}: Found {len(ids_found)} IDs ({new_added} new). Total: {len(collected_ids)} / {target_count}"
#                         )

#                         # update progress bar
#                         pbar.update(new_added)

#                         with versioner.write_to_temp() as temp_file:
#                             for game_id in collected_ids.keys():
#                                 temp_file.write(f"{game_id}\n")

#                         page += 1

#                         # RANDOMIZED HUMAN-LIKE DELAY
#                         sleep_time = random.uniform(5.2, 7.0)
#                         time.sleep(sleep_time)

#                     elif response.status_code == 429:
#                         tqdm.write(
#                             "  -> ERROR 429: Rate limited! Sleeping for 60 seconds..."
#                         )
#                         time.sleep(60)
#                         continue
                        
#                     elif "Just a moment..." in response.text:
#                         tqdm.write(
#                             f"  -> ERROR: Cloudflare block detected on page {page}. Your cf_clearance cookie has likely expired."
#                         )
#                         break

#                     else:
#                         tqdm.write(
#                             f"Failed to load page {page}. Status code: {response.status_code}"
#                         )
#                         break

#                 except Exception as e:
#                     tqdm.write(f"Error occurred on page {page}: {e}")
#                     break

#             # VERSIONING: Once the loop finishes, rename the temp file with a new timestamp
#             versioner.dump_temp_to_final()


# if __name__ == "__main__":
#     harvest_game_ids(
#         target_count=args.target,
#         start_page=args.start_page,
#         smart_append=args.smart_append,
#     )
import os
import random
import re
import time
from argparse import ArgumentParser
from playwright.sync_api import sync_playwright
from tqdm import tqdm

from src.properties import safe_interrupt_handler
from src.config import DATA_DIR, HARVEST_FILE_NAME, HARVEST_TEMP_FILE
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


def harvest_game_ids(target_count=TARGET_GAME_COUNT, start_page=1, smart_append=False):
    collected_ids = {}
    page = start_page
    versioner = SmartVersioner(base_filename=HARVEST_FILE_NAME.stem, data_dir=DATA_DIR)

    # --- SMART APPENDING (CHECKPOINTING) ---
    if smart_append:
        tqdm.write("Smart appending enabled. Checking for existing checkpoint files...")
        versioner.append_existing_ids(
            collected_ids, target_count=target_count, delimiter="\t", id_column_index=0
        )

    tqdm.write(f"\n--- STARTING GAME ID COLLECTION VIA CDP (Target: {target_count}) ---")
    tqdm.write(f"Writing to temporary safe file: {HARVEST_TEMP_FILE.name}")

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
        target_count=args.target,
        start_page=args.start_page,
        smart_append=args.smart_append,
    )