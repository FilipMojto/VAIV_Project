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


def _extract_publication_history(wiki_text: str) -> str | None:
    """Extract publication details from the article's Publication section."""

    heading_match = re.search(
        r"^(={2,6})\s*Publication(?:\s+history)?\s*\1\s*$",
        wiki_text,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    if not heading_match:
        return None

    heading_level = len(heading_match.group(1))
    section_start = heading_match.end()

    # Stop at the next heading of the same or higher level.
    next_heading = re.compile(
        r"^(={2,6})\s*.*?\s*\1\s*$",
        flags=re.MULTILINE,
    )

    section_end = len(wiki_text)

    for match in next_heading.finditer(wiki_text, section_start):
        if len(match.group(1)) <= heading_level:
            section_end = match.start()
            break

    section = wiki_text[section_start:section_end]
    entries = []

    for line in section.splitlines():
        line = line.strip()

        if not line:
            continue

        # Extract list entries.
        list_match = re.match(r"^[*#]+\s*(.+)$", line)

        if list_match:
            value = _clean_wiki_value(list_match.group(1))
            if value:
                value = re.sub(r"\[\s*\d+\s*\]", "", value)
                entries.append(value.strip())
            continue

        # Extract data cells from wiki tables.
        if line.startswith("|") and not line.startswith("|}"):
            cells = re.split(r"\|\||!!", line.lstrip("|"))

            for cell in cells:
                value = _clean_wiki_value(cell)

                if value:
                    value = re.sub(r"\[\s*\d+\s*\]", "", value)
                    value = value.strip()

                    if value:
                        entries.append(value)

    # Remove duplicates while preserving order.
    entries = list(dict.fromkeys(entries))

    return " | ".join(entries) if entries else None


def _extract_infobox_publication_history(value: str) -> str | None:
    """Extract edition history from an infobox date parameter."""

    if not value:
        return None

    value = html.unescape(value)
    value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)

    # Remove references before processing the edition entries.
    value = re.sub(
        r"<ref\b[^>]*>.*?</ref>",
        "",
        value,
        flags=re.DOTALL | re.IGNORECASE,
    )
    value = re.sub(
        r"<ref\b[^>]*/\s*>",
        "",
        value,
        flags=re.IGNORECASE,
    )

    # Replace Wikipedia date templates with their year.
    value = re.sub(
        r"\{\{\s*start date(?: and age)?\s*\|\s*(\d{4})(?:\s*\|[^{}]*)?\}\}",
        r"\1",
        value,
        flags=re.IGNORECASE,
    )

    # Remove the plainlist wrapper while retaining its contents.
    value = re.sub(
        r"^\s*\{\{\s*plainlist\s*\|",
        "",
        value,
        count=1,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\}\}\s*$", "", value)

    entries = []

    for line in value.splitlines():
        line = line.strip()

        if not line:
            continue

        match = re.match(r"^[*#]+\s*(.+)$", line)

        if match:
            line = match.group(1)

        cleaned = _clean_wiki_value(line)

        if cleaned:
            entries.append(cleaned)

    # Remove duplicates without changing the original order.
    entries = list(dict.fromkeys(entries))

    return " | ".join(entries) if entries else None


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



def _extract_official_website(parameters: dict[str, str]) -> str | None:
    """Extract and normalize a website URL from an infobox parameter."""

    for alias in ("official website", "website", "url", "web"):
        value = parameters.get(alias)

        if not value:
            continue

        # Handle Wikipedia's {{URL|example.com}} template.
        template_match = re.search(
            r"\{\{\s*URL\s*\|\s*([^|{}]+)",
            value,
            flags=re.IGNORECASE,
        )

        if template_match:
            value = template_match.group(1).strip()
        else:
            # Handle ordinary explicit URLs.
            url_match = re.search(
                r"https?://[^\s|<>{}\]]+",
                value,
                flags=re.IGNORECASE,
            )

            if url_match:
                return url_match.group(0).rstrip(".,;")

            # Clean other simple wikitext representations.
            value = _clean_wiki_value(value) or ""

        value = value.strip()

        if re.fullmatch(
            r"(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s]*)?",
            value,
            flags=re.IGNORECASE,
        ):
            return f"https://{value}"

    return None



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
        "publication_history": None,
        "setup_time": None,
        "chance": None,
        "official_website": None,
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


    is_game_infobox = (infobox_type or "").casefold() == "game"

    field_aliases = {
        "designer": ("designer", "designers"),
        "publisher": ("publisher", "publishers"),
        "release_date": (
            "released",
            "release date",
            "release_date",
            "publication",
        ) + (() if is_game_infobox else ("date",)),
        "number_of_players": ("players", "number of players"),
        "playing_time": ("playing time", "playing_time"),
        "publication_history": (
            "publication history",
            "editions",
            "released",
        ) + (("date",) if is_game_infobox else ("publication",)),
        "setup_time": ("setup time", "setup_time", "setup"),
        "chance": (
            "random chance",
            "random_chance",
            "randomness",
            "chance",
        ),
    }


    for output_field, aliases in field_aliases.items():
        for alias in aliases:
            value = parameters.get(alias)

            if value:
                if (
                    output_field == "publication_history"
                    and is_game_infobox
                    and alias == "date"
                ):
                    result[output_field] = (
                        _extract_infobox_publication_history(value)
                    )
                else:
                    result[output_field] = _clean_wiki_value(value)

                break



    if result["publication_history"] is None:
        result["publication_history"] = _extract_publication_history(
            wiki_text
        )
    result["official_website"] = _extract_official_website(parameters)

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
    wiki_text = revision.findtext("text") if revision is not None else None

    return {
        "wiki_page_id": page_id,
        "wiki_title": title,
        "wiki_namespace": int(namespace),
        "wiki_text": wiki_text,
    }
