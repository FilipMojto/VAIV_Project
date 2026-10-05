

from pathlib import Path

from playwright.sync_api import sync_playwright
from tqdm import tqdm


import time

from src.config import CDP_URL, HTML_DIR

def scrape_page(app_id: str, file_path: str, browser=None):

    # Ak HTML nemáme a Playwright ešte nebeží, pripoj sa (Lazy načítanie)
    with sync_playwright() as p:
        if browser is None:
            try:
                browser = p.chromium.connect_over_cdp(CDP_URL)
                context = browser.contexts[0]
                browser_page = (
                    context.pages[0]
                    if context.pages
                    else context.new_page()
                )
            except Exception as e:
                tqdm.write(
                    f"[ERROR] Could not connect to Chrome on {CDP_URL}! Details: {e}"
                )
                return

        tqdm.write(
            f"Fetching HTML for app_id {app_id} via CDP..."
        )
        url = f"https://boardgamegeek.com/boardgame/{app_id}/"

        try:
            # Prejdeme na stránku a počkáme na stiahnutie Javascriptových dát
            # browser_page.goto(url, wait_until="networkidle", timeout=30000)
            # time.sleep(2)  # Krátky delay pre vyrenderovanie komponentov
            # OPRAVENÝ KÓD
            # domcontentloaded načíta štruktúru bez čakania na reklamy a trackery
            browser_page.goto(
                url, wait_until="domcontentloaded", timeout=30000
            )

            # Ak chceš mať istotu, že sa načítali dáta hry, počkáme, kým sa zjaví hlavný nadpis
            try:
                # Čakáme max 5 sekúnd na vyrenderovanie elementu, ktorý obsahuje rok alebo názov
                browser_page.wait_for_selector(
                    "span.game-year", timeout=5000
                )
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
            # continue

if __name__ == "__main__":
    # Testovanie funkcie scrape_page
    test_app_id = "436560"  # Zadaj platné app_id pre test
    test_file_path = Path(HTML_DIR / f"test_{test_app_id}.html")
    scrape_page(test_app_id, test_file_path)
    tqdm.write(f"HTML for app_id {test_app_id} saved to {test_file_path}")