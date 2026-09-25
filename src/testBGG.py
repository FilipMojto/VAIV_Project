
# import re
# import requests

# # Paste your exact values from your real browser here
# CF_CLEARANCE = "G0txBTPBLgY4sVXlxtA_iyJLX2YF30HIHTB8OfZR5II-1790375641-1.2.1.1-83fY7WzD76aOdiG6DAiIF4ZokncdGn4g.ulf59YqUOa05cgOHHqXrJl6XmLYAyHvhU2n7C0MB3MvpacdNl1yYJuta_pclIxrYcdUZ0tX0EYlFtxf5NpsDKLcK2xQK_oOcel_eVTaAwssPw1U97fRb429MXqB0uqURwqog4oDUkHwUspaquhtFauZpA_iDcF3iAZ2r1A4EBJ6KRDnF7QoBBviYgaZNTn65o87xUmuVxOm1SXbDIf9Gj2i9KVcYDaVAqKlXVUDplxFcB_49ou893aHhKRvSc65EcMgxVM2nVQVrHQF5IqEgaMUHlTyoKRrKIF.aD38fL086AIj9Z.S3WUQRwdRiwKeRWDwTg2WSeNf7jQ1z8gBpw9F9xWz0YSYdxX5OyUOKZQ3xSrlQRGJDVptfsxWkefOqjSPulTEzvvoD.2kaYfmna4VNrOSBrrhd4oLcwPv6amYdyJsdBu4s3y.APBfTGoadq7LRjvS5g9pZcDOPz.hJAS6D9Mx54Nqgrw2A7m9ZF7GtiBEWN4K3gUG7XsuO1gx8_PHmr8EkKN1Mm3qxySOYrPJ5jeAgYRSjAxnDsunu7ieS343e7xd0HbqOAowL2JpoyAvzskWVmi2KjTKsqpmXOYWWvqFto_1"
# USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36'

# session = requests.Session()
# session.headers.update({
#     "User-Agent": USER_AGENT,
#     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
#     "Accept-Language": "en-US,en;q=0.9",
# })

# # Inject the clearance cookie into the session
# session.cookies.set("cf_clearance", CF_CLEARANCE, domain=".boardgamegeek.com")

# def fetch_and_parse_game(game_id: str):
#     url = f"https://boardgamegeek.com/boardgame/{game_id}"
#     print("Current session cookies:", session.cookies.get_dict())
#     print(f"Fetching raw HTML for game {game_id}...")
    
#     response = session.get(url, timeout=15)
    
#     if response.status_code == 200 and "Just a moment..." not in response.text:
#         print(f"-> SUCCESS! Received {len(response.text):,} characters.")
        
#         # Save raw HTML to satisfy the "Stiahnutie stránok" course requirement
#         with open(f"{game_id}.html", "w", encoding="utf-8") as f:
#             f.write(response.text)
            
#         # Parse fields using pure regex (re)
#         title_match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', response.text)
#         title = title_match.group(1) if title_match else "Unknown"
        
#         print(f"Extracted Title: {title}")
#         return True
#     else:
#         print(f"-> BLOCKED (Status: {response.status_code}). Cookie may have expired.")
#         return False

# if __name__ == "__main__":
#     fetch_and_parse_game("224517")
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