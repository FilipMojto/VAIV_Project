"""Tests for incremental Wikipedia page extraction."""

import unittest
import xml.etree.ElementTree as ET
from src.wiki_extraction import (
    WikipediaPageParser,
    build_wikipedia_title_index,
    extract_page_records,
    extract_wikipedia_game_fields,
    parse_wikipedia_page,
    extract_redirect_target,
    resolve_redirect_target,
)


def test_parse_wiki_page_extracts_page_metadata_and_text():
    page_xml = """
    <page>
        <title>Catan</title>
        <ns>0</ns>
        <id>12345</id>
        <revision>
            <id>98765</id>
            <text>Article content about Catan.</text>
        </revision>
    </page>
    """

    result = parse_wikipedia_page(page_xml)

    assert result == {
        "wiki_page_id": "12345",
        "wiki_title": "Catan",
        "wiki_namespace": 0,
        "wiki_text": "Article content about Catan.",
    }


def test_parse_wiki_page_handles_missing_article_text():
    page_xml = """
    <page>
        <title>Example</title>
        <ns>0</ns>
        <id>123</id>
        <revision>
            <id>456</id>
        </revision>
    </page>
    """

    result = parse_wikipedia_page(page_xml)

    assert result["wiki_page_id"] == "123"
    assert result["wiki_text"] is None


def test_parse_wiki_page_preserves_non_main_namespace():
    page_xml = """
    <page>
        <title>Category:Board games</title>
        <ns>14</ns>
        <id>789</id>
        <revision>
            <id>456</id>
            <text>Category content.</text>
        </revision>
    </page>
    """

    result = parse_wikipedia_page(page_xml)

    assert result["wiki_namespace"] == 14


def test_parse_wiki_page_returns_none_for_missing_metadata():
    page_xml = """
    <page>
        <title>Example</title>
        <ns>0</ns>
    </page>
    """

    assert parse_wikipedia_page(page_xml) is None


def test_parse_wiki_page_decodes_xml_entities():
    page_xml = """
    <page>
        <title>Tom &amp; Jerry</title>
        <ns>0</ns>
        <id>123</id>
        <revision>
            <text>Tom &amp; Jerry &lt;3</text>
        </revision>
    </page>
    """

    result = parse_wikipedia_page(page_xml)

    assert result["wiki_title"] == "Tom & Jerry"
    assert result["wiki_text"] == "Tom & Jerry <3"


def test_parse_wiki_page_raises_for_malformed_xml():
    page_xml = """
    <page>
        <title>Example</title>
        <ns>0</ns>
        <id>123</id>
    """

    with unittest.TestCase().assertRaises(ET.ParseError):
        parse_wikipedia_page(page_xml)


def test_extract_redirect_target():
    assert (
        extract_redirect_target("#REDIRECT [[Hotel (board game)]]")
        == "Hotel (board game)"
    )


def test_extract_redirect_target_is_case_insensitive():
    assert (
        extract_redirect_target("#redirect [[Hotel]]")
        == "Hotel"
    )


def test_extract_redirect_target_handles_whitespace():
    assert (
        extract_redirect_target("  #REDIRECT  [[  Hotel  ]]")
        == "Hotel"
    )


def test_extract_redirect_target_replaces_underscores():
    assert (
        extract_redirect_target("#REDIRECT [[Board_game]]")
        == "Board game"
    )


def test_extract_redirect_target_ignores_section_fragment():
    assert (
        extract_redirect_target("#REDIRECT [[Hotel#History]]")
        == "Hotel"
    )


def test_extract_redirect_target_ignores_display_text():
    assert (
        extract_redirect_target("#REDIRECT [[Hotel|the hotel game]]")
        == "Hotel"
    )


def test_extract_redirect_target_returns_none_for_regular_article():
    assert extract_redirect_target("Hotel is a board game.") is None


def test_extract_redirect_target_returns_none_for_missing_text():
    assert extract_redirect_target(None) is None

def test_resolve_redirect_target_exact_match():
    pages = [
        {"wiki_page_id": "100", "wiki_title": "Hotel (board game)"},
    ]

    # result = resolve_redirect_target("Hotel (board game)", pages)
    title_index = build_wikipedia_title_index(pages)
    result = resolve_redirect_target("Hotel (board game)", title_index)

    assert result == {
        "redirect_status": "resolved",
        "redirect_target_page_id": "100",
    }


def test_resolve_redirect_target_prefers_exact_case_match():
    pages = [
        {"wiki_page_id": "100", "wiki_title": "Target"},
        {"wiki_page_id": "200", "wiki_title": "target"},
    ]

    title_index = build_wikipedia_title_index(pages)
    result = resolve_redirect_target("Target", title_index)

    assert result == {
        "redirect_status": "resolved",
        "redirect_target_page_id": "100",
    }


def test_resolve_redirect_target_uses_first_letter_capitalization():
    pages = [
        {"wiki_page_id": "100", "wiki_title": "Target"},
    ]

    title_index = build_wikipedia_title_index(pages)
    result = resolve_redirect_target("target", title_index)

    assert result == {
        "redirect_status": "resolved",
        "redirect_target_page_id": "100",
    }


def test_resolve_redirect_target_returns_unresolved():
    pages = [
        {"wiki_page_id": "100", "wiki_title": "Other"},
    ]

    title_index = build_wikipedia_title_index(pages)
    result = resolve_redirect_target("Missing", title_index)

    assert result == {
        "redirect_status": "unresolved",
        "redirect_target_page_id": None,
    }


def test_resolve_redirect_target_returns_ambiguous_for_duplicate_titles():
    pages = [
        {"wiki_page_id": "100", "wiki_title": "Target"},
        {"wiki_page_id": "200", "wiki_title": "Target"},
    ]

    title_index = build_wikipedia_title_index(pages)
    result = resolve_redirect_target("Target", title_index)

    assert result == {
        "redirect_status": "ambiguous",
        "redirect_target_page_id": None,
    }


def test_resolve_redirect_target_deduplicates_same_page_id():
    pages = [
        {"wiki_page_id": "100", "wiki_title": "Target"},
        {"wiki_page_id": "100", "wiki_title": "Target"},
    ]

    title_index = build_wikipedia_title_index(pages)
    result = resolve_redirect_target("Target", title_index)

    assert result == {
        "redirect_status": "resolved",
        "redirect_target_page_id": "100",
    }

def test_supports_publication_parameter_for_release_date():
    text = """
    {{Infobox game
    | publication = 1986
    }}
    """

    result = extract_wikipedia_game_fields(text)

    assert result["release_date"] == "1986"

class TestWikipediaPageParser(unittest.TestCase):

    def test_extracts_complete_page(self):
        lines = [
            "<mediawiki>\n",
            "<page>\n",
            "<title>Example</title>\n",
            "</page>\n",
            "</mediawiki>\n",
        ]

        pages = list(extract_page_records(lines))

        self.assertEqual(
            pages,
            [
                "<page>\n"
                "<title>Example</title>\n"
                "</page>"
            ],
        )

    def test_extracts_multiple_pages(self):
        lines = [
            "<mediawiki>\n",
            "<page><title>First</title></page>\n",
            "<page><title>Second</title></page>\n",
            "</mediawiki>\n",
        ]

        pages = list(extract_page_records(lines))

        self.assertEqual(
            pages,
            [
                "<page><title>First</title></page>",
                "<page><title>Second</title></page>",
            ],
        )

    def test_extracts_page_split_between_two_chunks(self):
        parser = WikipediaPageParser()

        first_chunk = [
            "<page>\n",
            "<title>Example</title>\n",
            "<text>Beginning of content\n",
        ]

        second_chunk = [
            "End of content</text>\n",
            "</page>\n",
        ]

        first_result = list(parser.feed(first_chunk))
        second_result = list(parser.feed(second_chunk))
        parser.finish()

        self.assertEqual(first_result, [])
        self.assertEqual(
            second_result,
            [
                "<page>\n"
                "<title>Example</title>\n"
                "<text>Beginning of content\n"
                "End of content</text>\n"
                "</page>"
            ],
        )

    def test_extracts_page_split_across_three_chunks(self):
        parser = WikipediaPageParser()

        chunks = [
            [
                "<page>\n",
                "<title>Example</title>\n",
                "<text>Beginning\n",
            ],
            [
                "Middle of the content\n",
            ],
            [
                "End of the content</text>\n",
                "</page>\n",
            ],
        ]

        pages = []

        for chunk in chunks:
            pages.extend(parser.feed(chunk))

        parser.finish()

        self.assertEqual(len(pages), 1)
        self.assertIn("<title>Example</title>", pages[0])
        self.assertIn("Beginning\nMiddle of the content\n", pages[0])
        self.assertIn("End of the content</text>", pages[0])
        self.assertTrue(pages[0].endswith("</page>"))

    def test_partition_can_finish_one_page_and_start_another(self):
        parser = WikipediaPageParser()

        # Simulates a partition that begins with the end of one page
        # and contains the beginning of the next page.
        first_chunk = [
            "<page><title>First</title>\n",
        ]

        second_chunk = [
            "</page>\n",
            "<page><title>Second</title>\n",
            "<text>Second page continues\n",
        ]

        third_chunk = [
            "</text></page>\n",
        ]

        pages = []
        pages.extend(parser.feed(first_chunk))
        pages.extend(parser.feed(second_chunk))
        pages.extend(parser.feed(third_chunk))
        parser.finish()

        self.assertEqual(
            pages,
            [
                "<page><title>First</title>\n</page>",
                "<page><title>Second</title>\n"
                "<text>Second page continues\n</text></page>",
            ],
        )

    def test_extracts_multiple_pages_on_the_same_line(self):
        lines = [
            "<page><title>First</title></page>"
            "<page><title>Second</title></page>\n"
        ]

        pages = list(extract_page_records(lines))

        self.assertEqual(
            pages,
            [
                "<page><title>First</title></page>",
                "<page><title>Second</title></page>",
            ],
        )

    def test_ignores_content_outside_page_elements(self):
        lines = [
            "<?xml version='1.0'?>\n",
            "<mediawiki>\n",
            "<siteinfo>Metadata</siteinfo>\n",
            "<page><title>Example</title></page>\n",
            "</mediawiki>\n",
        ]

        pages = list(extract_page_records(lines))

        self.assertEqual(
            pages,
            ["<page><title>Example</title></page>"],
        )

    def test_handles_empty_input(self):
        self.assertEqual(list(extract_page_records([])), [])

    def test_handles_input_without_pages(self):
        lines = [
            "<?xml version='1.0'?>\n",
            "<mediawiki>\n",
            "</mediawiki>\n",
        ]

        self.assertEqual(list(extract_page_records(lines)), [])

    def test_raises_for_unfinished_page(self):
        lines = [
            "<page>\n",
            "<title>Incomplete</title>\n",
        ]

        with self.assertRaisesRegex(ValueError, "closing </page>"):
            list(extract_page_records(lines))

    def test_raises_for_nested_page(self):
        lines = [
            "<page>\n",
            "<page><title>Nested</title></page>\n",
            "</page>\n",
        ]

        with self.assertRaisesRegex(ValueError, "nested"):
            list(extract_page_records(lines))

    def test_raises_for_unmatched_closing_tag(self):
        lines = [
            "</page>\n",
        ]

        with self.assertRaisesRegex(ValueError, "without a corresponding"):
            list(extract_page_records(lines))


if __name__ == "__main__":
    unittest.main()
