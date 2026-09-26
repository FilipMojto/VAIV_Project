import time
import os
from playwright.sync_api import sync_playwright

# List of Game IDs to download
GAME_IDS = ["224517", "342942", "161936"]
OUTPUT_DIR = "data/raw_html"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def harvest_raw_html():
    with sync_playwright() as p:
        # Attach to your running, authenticated Chrome browser
        print("Connecting to running Chrome instance on port 9222...")
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        
        # Use the existing open context/tab
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()

        for game_id in GAME_IDS:
            file_path = os.path.join(OUTPUT_DIR, f"{game_id}.html")
            
            # Skip if already downloaded
            if os.path.exists(file_path):
                print(f"Skipping {game_id}: Already saved.")
                continue

            url = f"https://boardgamegeek.com/boardgame/{game_id}"
            print(f"Navigating to {url}...")
            
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait brief moment for dynamic elements
            time.sleep(2)
            
            # Extract raw page HTML
            html_content = page.content()

            if "Just a moment..." in page.title():
                print(f"-> Cloudflare triggered on {game_id}! Please solve it in the Chrome window.")
                # Pause and wait until you click the box manually
                while "Just a moment..." in page.title():
                    time.sleep(2)

            # Save to disk
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
                
            print(f"-> SUCCESS: Saved {len(html_content):,} characters to {file_path}")
            
            # Polite human-like delay
            time.sleep(3)

if __name__ == "__main__":
    harvest_raw_html()