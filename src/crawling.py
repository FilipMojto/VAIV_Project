from pathlib import Path
import time
from typing import Callable

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)
from tqdm import tqdm

from src.config import CDP_URL, OUTPUT_DIR
from src.utils import load_html_file


class BrowserConnectionError(RuntimeError):
    """Raised when the crawler cannot use its remote Chrome connection."""


class PageHTMLFetcher:
    def __init__(
        self,
        log_func: Callable[[str], None] = print,
        connect_timeout_ms: int = 15_000,
    ):
        self.log_func = log_func
        self.connect_timeout_ms = connect_timeout_ms
        self._playwright = None
        self._browser = None
        self._page = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
            self._browser = None
            self._page = None

    def _connect(self):
        if self._browser is not None and self._browser.is_connected():
            return

        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

        self.log_func(f"Connecting to Chrome on {CDP_URL}...")
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(
                CDP_URL, timeout=self.connect_timeout_ms
            )
            if not self._browser.contexts:
                raise BrowserConnectionError(
                    "Connected to Chrome, but it has no browser context."
                )

            context = self._browser.contexts[0]
            self._page = context.pages[0] if context.pages else context.new_page()
        except BrowserConnectionError:
            raise
        except PlaywrightError as exc:
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None
            self._browser = None
            self._page = None
            raise BrowserConnectionError(
                f"Could not connect to Chrome on {CDP_URL} within "
                f"{self.connect_timeout_ms / 1000:g} seconds: {exc}"
            ) from exc

    @staticmethod
    def _is_cloudflare_block(html_content: str) -> bool:
        return (
            "Attention Required! | Cloudflare" in html_content
            or "Just a moment..." in html_content
        )

    def get_html(self, page_id: int) -> str:
        file_path = Path(OUTPUT_DIR) / f"{page_id}.html"

        if file_path.exists():
            self.log_func(f"Page {page_id} found in cache. Loading...")
            html_content = load_html_file(app_id=str(page_id))
            if not self._is_cloudflare_block(html_content):
                self.log_func(f"Loading valid cached HTML for app_id {page_id}...")
                return html_content
            self.log_func(
                f"Cached HTML for app_id {page_id} is blocked by Cloudflare; "
                "fetching it again."
            )

        self._connect()
        url = f"https://boardgamegeek.com/boardgame/{page_id}/"
        try:
            self.log_func(f"Fetching HTML for app_id {page_id} via CDP...")
            self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            try:
                self._page.wait_for_selector("span.game-year", timeout=5_000)
            except PlaywrightTimeoutError:
                pass

            if "Just a moment..." in self._page.title():
                self.log_func(
                    f"Cloudflare challenge on {url}; solve it in Chrome "
                    "within 120 seconds."
                )
                deadline = time.monotonic() + 120
                while (
                    "Just a moment..." in self._page.title()
                    and time.monotonic() < deadline
                ):
                    time.sleep(2)
                if "Just a moment..." in self._page.title():
                    raise RuntimeError(
                        f"Cloudflare challenge was not solved for {url}"
                    )

            html_content = self._page.content()
            if not html_content or self._is_cloudflare_block(html_content):
                raise RuntimeError(f"Could not retrieve usable HTML for {url}")

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(html_content, encoding="utf-8")
            return html_content
        except PlaywrightError as exc:
            if self._browser is None or not self._browser.is_connected():
                raise BrowserConnectionError(
                    f"Lost the Chrome connection while loading {url}: {exc}"
                ) from exc
            raise RuntimeError(f"Error fetching {url}: {exc}") from exc


def crawl_page_html(page_id: int, log_func: Callable[[str], None] = print) -> str:
    """Fetch one page using a short-lived CDP connection."""
    with PageHTMLFetcher(log_func=log_func) as fetcher:
        return fetcher.get_html(page_id)
