"""Utilities for extracting complete Wikipedia page records from XML text."""

import re
from collections.abc import Iterable, Iterator
import xml.etree.ElementTree as ET
import html

_PAGE_TAG_PATTERN = re.compile(r"</?page\b[^>]*>", re.IGNORECASE)

_REDIRECT_PATTERN = re.compile(
    r"^\s*#redirect\s*\[\[\s*([^\]|#]+)",
    re.IGNORECASE,
)

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

def extract_redirect_target(text: str | None) -> str | None:
    """Extract the target title from a Wikipedia redirect."""

    if not text:
        return None

    match = _REDIRECT_PATTERN.match(text)

    if match is None:
        return None

    target = match.group(1).strip().replace("_", " ")

    return target or None


def build_wikipedia_title_index(
    pages: Iterable[dict[str, str]],
) -> dict[str, set[str]]:
    """Build an index mapping Wikipedia titles to page IDs."""

    title_index: dict[str, set[str]] = {}

    for page in pages:
        title = page["wiki_title"]
        page_id = page["wiki_page_id"]

        title_index.setdefault(title, set()).add(page_id)

    return title_index


def resolve_redirect_target(
    target: str,
    title_index: dict[str, set[str]],
) -> dict[str, str | None]:
    """Resolve a redirect target using a Wikipedia title index."""

    matches = title_index.get(target, set())

    if not matches and target:
        capitalized_target = target[0].upper() + target[1:]
        matches = title_index.get(capitalized_target, set())

    if len(matches) == 1:
        return {
            "redirect_status": "resolved",
            "redirect_target_page_id": next(iter(matches)),
        }

    if len(matches) > 1:
        return {
            "redirect_status": "ambiguous",
            "redirect_target_page_id": None,
        }

    return {
        "redirect_status": "unresolved",
        "redirect_target_page_id": None,
    }


def _clean_wiki_value(value: str) -> str | None:
    """Convert a basic wikitext field value into readable plain text."""

    if not value:
        return None

    value = html.unescape(value)
    value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    value = re.sub(r"<ref\b[^>]*>.*?</ref>", "", value, flags=re.DOTALL | re.IGNORECASE)
    value = re.sub(r"<ref\b[^>]*/\s*>", "", value, flags=re.IGNORECASE)

    # Remove simple nested templates, working from the innermost outward.
    # Unwrap simple templates while preserving their parameter contents.
    previous = None
    while previous != value:
        previous = value

        value = re.sub(
            r"\{\{\s*[^{}|]+\|([^{}]*)\}\}",
            r"\1",
            value,
        )

        # Remove templates without parameters.
        value = re.sub(r"\{\{[^{}]*\}\}", "", value)

    # Convert wiki links to their displayed text.
    value = re.sub(
        r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]",
        r"\1",
        value,
    )
    value = re.sub(r"\[https?://[^\s\]]+\s*([^\]]*)\]", r"\1", value)

    value = re.sub(r"'''?", "", value)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[\[\]{}]", "", value)
    value = re.sub(r"\s+", " ", value)

    value = value.strip(" \t\r\n|")

    return value or None


def _extract_infobox_parameters(text: str) -> tuple[str | None, dict[str, str]]:
    """Extract parameters from the first Infobox template."""

    match = re.search(
        r"\{\{\s*Infobox\s+([^\n|}]+)",
        text,
        flags=re.IGNORECASE,
    )

    if match is None:
        return None, {}

    infobox_type = match.group(1).strip()
    depth = 1
    parameters: dict[str, str] = {}
    current_key = None
    current_value: list[str] = []

    # Process lines after the opening Infobox declaration.
    remaining = text[match.end():]

    for line in remaining.splitlines():
        parameter_match = None

        if depth == 1:
            parameter_match = re.match(
                r"^\s*\|\s*([^=]+?)\s*=\s*(.*)$",
                line,
            )

        if parameter_match:
            if current_key is not None:
                parameters[current_key] = "\n".join(current_value).strip()

            current_key = parameter_match.group(1).strip().lower()
            current_value = [parameter_match.group(2)]
        elif current_key is not None:
            current_value.append(line)

        depth += line.count("{{") - line.count("}}")

        if depth <= 0:
            break

    if current_key is not None:
        parameters[current_key] = "\n".join(current_value).strip()

    return infobox_type, parameters


def extract_wikipedia_game_fields(
    wiki_text: str | None,
) -> dict[str, str | None]:
    """Extract selected game-related fields from Wikipedia wikitext."""

    result = {
        "short_description": None,
        "infobox_type": None,
        "designer": None,
        "publisher": None,
        "release_date": None,
        "number_of_players": None,
        "playing_time": None,
    }

    if not wiki_text:
        return result

    short_description_match = re.search(
        r"\{\{\s*short description\s*\|\s*(.*?)\s*\}\}",
        wiki_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if short_description_match:
        result["short_description"] = _clean_wiki_value(
            short_description_match.group(1)
        )

    infobox_type, parameters = _extract_infobox_parameters(wiki_text)
    result["infobox_type"] = infobox_type

    field_aliases = {
        "designer": ("designer", "designers"),
        "publisher": ("publisher", "publishers"),
        "release_date": (
            "released",
            "release date",
            "release_date",
            "date",
            "publication",
        ),
        "number_of_players": ("players", "number of players"),
        "playing_time": ("playing time", "playing_time"),
    }

    for output_field, aliases in field_aliases.items():
        for alias in aliases:
            value = parameters.get(alias)

            if value:
                result[output_field] = _clean_wiki_value(value)
                break

    return result


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
