"""Utilities for extracting complete Wikipedia page records from XML text."""

import re
from collections.abc import Iterable, Iterator
import xml.etree.ElementTree as ET


_PAGE_TAG_PATTERN = re.compile(r"</?page\b[^>]*>", re.IGNORECASE)


class WikipediaPageParser:
    """Incrementally reconstruct complete Wikipedia page XML elements.

    The parser retains its state between calls to feed(), so a page can
    begin in one input chunk and finish in a later chunk.
    """

    def __init__(self) -> None:
        self._inside_page = False
        self._page_parts: list[str] = []

    def feed(self, lines: Iterable[str]) -> Iterator[str]:
        """Process input lines and yield every complete page encountered."""

        for line in lines:
            matches = list(_PAGE_TAG_PATTERN.finditer(line))

            if not matches:
                if self._inside_page:
                    self._page_parts.append(line)
                continue

            cursor = 0

            for match in matches:
                tag = match.group(0)
                is_closing_tag = tag.startswith("</")

                if not self._inside_page:
                    if is_closing_tag:
                        raise ValueError(
                            "Encountered a closing </page> tag "
                            "without a corresponding opening tag."
                        )

                    # Ignore everything before the opening page tag.
                    self._inside_page = True
                    self._page_parts = [tag]
                    cursor = match.end()
                    continue

                if not is_closing_tag:
                    raise ValueError(
                        "Encountered a nested <page> tag before "
                        "the previous page was closed."
                    )

                # Include everything up to and including </page>.
                self._page_parts.append(line[cursor:match.end()])

                yield "".join(self._page_parts)

                self._inside_page = False
                self._page_parts = []
                cursor = match.end()

            # Preserve the remainder if a page is still being assembled.
            if self._inside_page:
                self._page_parts.append(line[cursor:])

    def finish(self) -> None:
        """Validate that the input ended outside a page element."""

        if self._inside_page:
            raise ValueError(
                "Input ended before the current Wikipedia page "
                "reached its closing </page> tag."
            )


def extract_page_records(lines: Iterable[str]) -> Iterator[str]:
    """Extract complete page elements from a sequential stream of lines."""

    parser = WikipediaPageParser()

    yield from parser.feed(lines)

    parser.finish()


def parse_wikipedia_page(page_xml: str) -> dict | None:
    """
    Extract metadata and article text from one complete Wikipedia page.

    Returns None if the page does not contain the required metadata.
    Namespace filtering is performed separately.
    """
    root = ET.fromstring(page_xml)

    title = root.findtext("title")
    namespace = root.findtext("ns")
    page_id = root.findtext("id")

    if title is None or namespace is None or page_id is None:
        return None

    revision = root.find("revision")
    text = revision.findtext("text") if revision is not None else None

    return {
        "wiki_page_id": page_id,
        "wiki_title": title,
        "wiki_namespace": int(namespace),
        "wiki_text": text,
    }
