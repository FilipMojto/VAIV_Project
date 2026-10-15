import os
import time
from typing import Callable

from playwright.sync_api import sync_playwright
from tqdm import tqdm

from src.config import CDP_URL, OUTPUT_DIR
from src.utils import load_html_file


def crawl_page_html(page_id: int, log_func: Callable[[str], None] = print):
    file_path = os.path.join(OUTPUT_DIR, f"{page_id}.html")

    html_content = None
    # Skontroluj, či už je HTML lokálne uložené
    if os.path.exists(file_path):
        log_func(f"Page {page_id} found in the cache!. Loading...")
        # Najprv načítame obsah a skontrolujeme ho
        html_content = load_html_file(app_id=page_id)

        # Skontrolujeme, či lokálny súbor nie je zablokovaný Cloudflare
        if (
            "Attention Required! | Cloudflare" in html_content
            or "Just a moment..." in html_content
        ):
            tqdm.write(
                f"[ Local HTML for app_id {page_id} contains Cloudflare block. Forcing re-fetch..."
            )
            html_content = (
                None  # Zahodíme zlý obsah, čím vynútime spustenie 'else' vetvy
            )
        else:
            tqdm.write(
                f"Loading valid cached HTML for app_id {page_id}..."
            )

        return html_content
    # Inštancia Playwright mimo slučky, aby sme nadväzovali spojenie iba raz
    # Ak HTML nemáme (alebo bol vyhodnotený ako Cloudflare blok), stiahneme ho
    if not html_content:
        with sync_playwright() as p:
            browser = None
            browser_page = None

            # for idx, app_id in tqdm(
            #     enumerate(pending_app_ids, 1),
            #     total=len(pending_app_ids),
            #     desc="Processing Games",
            #     unit="game",
            # ):
            
    
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
                f"[Fetching HTML for app_id {page_id} via CDP..."
            )
            url = f"https://boardgamegeek.com/boardgame/{page_id}/"

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
                return html_content
            except Exception as e:
                tqdm.write(f"  -> Error fetching page: {e}")
                return None
                # continue