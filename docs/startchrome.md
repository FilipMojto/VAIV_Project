
# Opening chrome in Debug mode

We open it so that we can bypass BoardGameGeek's cloudflare and scrape data.

## Step-by-step procedure

1. Open powershell and execute the following command:

```{shell}
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\selenum\ChromeProfile"
```

2. In that newly opened Chrome window, go to [https://boardgamegeek.com/boardgame/224517](https://boardgamegeek.com/boardgame/224517).

2. Let Cloudflare verify you. Once the game page loads, leave the browser open.

3. Run the Scraper Script

    - Playwright connects to your running Chrome window, navigates to the game page, grabs the DOM HTML, and saves it directly to your disk.