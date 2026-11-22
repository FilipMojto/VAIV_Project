"""Tests for incremental Wikipedia page extraction."""

import unittest
import xml.etree.ElementTree as ET
from src.wiki_extraction import (
    WikipediaPageParser,
    extract_page_records,
    parse_wikipedia_page,
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
