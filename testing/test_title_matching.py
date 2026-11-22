"""Tests for Unicode decoding and BGG title matching."""

import unittest

from src.title_matching import (
    decode_unicode_escapes,
    get_title_variants,
    normalize_title,
    split_alternate_names,
    build_title_match_index
)


def test_build_index_includes_primary_title():
    records = [
        {
            "app_id": "13",
            "game_title": "Catan",
            "alternate_names": "",
        }
    ]

    result = build_title_match_index(records)

    assert result["catan"] == [
        {
            "app_id": "13",
            "game_title": "Catan",
            "matched_variant": "Catan",
            "variant_type": "primary",
        }
    ]


def test_build_index_includes_alternate_titles():
    records = [
        {
            "app_id": "13",
            "game_title": "Catan",
            "alternate_names": "The Settlers of Catan | Die Siedler von Catan",
        }
    ]

    result = build_title_match_index(records)

    assert "the settlers of catan" in result
    assert "die siedler von catan" in result

    assert result["the settlers of catan"][0]["variant_type"] == "alternate"


def test_build_index_preserves_title_collisions():
    records = [
        {"app_id": "100", "game_title": "Example Game", "alternate_names": ""},
        {"app_id": "200", "game_title": "Example Game", "alternate_names": ""},
    ]

    result = build_title_match_index(records)

    assert len(result["example game"]) == 2
    assert {match["app_id"] for match in result["example game"]} == {
        "100",
        "200",
    }


def test_build_index_deduplicates_variants_within_game():
    records = [
        {
            "app_id": "13",
            "game_title": "Catan",
            "alternate_names": "CATAN | Catan | The Settlers of Catan",
        }
    ]

    result = build_title_match_index(records)

    assert len(result["catan"]) == 1
    assert result["catan"][0]["variant_type"] == "primary"


def test_build_index_decodes_unicode_escapes():
    records = [
        {
            "app_id": "500",
            "game_title": "Cafe",
            "alternate_names": r"Caf\u00e9",
        }
    ]

    result = build_title_match_index(records)

    assert "café" in result
    assert result["café"][0]["matched_variant"] == "Café"


class TestUnicodeDecoding(unittest.TestCase):

    def test_decodes_unicode_escape(self):
        self.assertEqual(decode_unicode_escapes(r"Fl\u00fcgelschlag"), "Flügelschlag")

    def test_preserves_existing_unicode(self):
        self.assertEqual(decode_unicode_escapes("Flügelschlag"), "Flügelschlag")

    def test_decodes_mixed_unicode(self):
        self.assertEqual(
            decode_unicode_escapes(r"Flügelschlag \u041a\u0440\u044b\u043b\u044c\u044f"),
            "Flügelschlag Крылья",
        )

    def test_decodes_surrogate_pair(self):
        self.assertEqual(decode_unicode_escapes(r"\uD83D\uDE00"), "😀")

    def test_preserves_malformed_escape(self):
        self.assertEqual(decode_unicode_escapes(r"Game \u12G4"), r"Game \u12G4")

    def test_preserves_unpaired_surrogate_escape(self):
        self.assertEqual(decode_unicode_escapes(r"Game \uD83D"), r"Game \uD83D")

    def test_decodes_consecutive_surrogate_and_regular_escapes(self):
        self.assertEqual(
            decode_unicode_escapes(r"\uD83D\uDE00\u0020\u0041"),
            "😀 A",
        )


class TestTitleNormalization(unittest.TestCase):

    def test_normalizes_case(self):
        self.assertEqual(normalize_title("PANDEMIC"), "pandemic")

    def test_normalizes_punctuation_and_whitespace(self):
        self.assertEqual(
            normalize_title("Catan: Traveler – Compact Edition"),
            "catan traveler compact edition",
        )

    def test_preserves_accents(self):
        self.assertEqual(normalize_title("Flügelschlag"), "flügelschlag")
        self.assertNotEqual(
            normalize_title("Flügelschlag"),
            normalize_title("Flugelschlag"),
        )

    def test_normalizes_escaped_unicode(self):
        self.assertEqual(normalize_title(r"Feszt\u00e1v"), "fesztáv")
        self.assertEqual(
            normalize_title(r"\u041a\u0440\u044b\u043b\u044c\u044f"),
            "крылья",
        )

    def test_normalize_title_preserves_thai_combining_marks(self):
        self.assertEqual(
            normalize_title("ปีกปักษา"),
            "ปีกปักษา",
        )


    def test_normalize_title_preserves_devanagari_combining_marks(self):
        self.assertEqual(
            normalize_title("टेराफॉर्मिंग मार्स"),
            "टेराफॉर्मिंग मार्स",
        )

    def test_normalizes_fullwidth_characters(self):
        self.assertEqual(
            normalize_title("Ｃａｔａｎ"),
            "catan",
        )

    def test_excludes_titles_without_letters_or_numbers(self):
        self.assertEqual(normalize_title("!@#$%^&*"), "")

        result = build_title_match_index([
            {
                "app_id": "100",
                "game_title": "!!!",
                "alternate_names": "---",
            }
        ])

        self.assertEqual(result, {})


class TestAlternateNames(unittest.TestCase):

    def test_splits_pipe_separated_names(self):
        self.assertEqual(
            split_alternate_names(r"Feszt\u00e1v | Fl\u00fcgelschlag | Wingspan"),
            ["Fesztáv", "Flügelschlag", "Wingspan"],
        )

    def test_does_not_split_on_commas(self):
        self.assertEqual(
            split_alternate_names("Game, The | Another Game"),
            ["Game, The", "Another Game"],
        )

    def test_handles_empty_values(self):
        self.assertEqual(split_alternate_names(None), [])
        self.assertEqual(split_alternate_names(""), [])
        self.assertEqual(split_alternate_names(" | "), [])

    def test_build_index_preserves_shared_alternate_titles(self):
        records = [
            {
                "app_id": "100",
                "game_title": "Game A",
                "alternate_names": "Shared Name",
            },
            {
                "app_id": "200",
                "game_title": "Game B",
                "alternate_names": "Shared Name",
            },
        ]

        result = build_title_match_index(records)

        matches = result["shared name"]

        assert len(matches) == 2
        assert {match["app_id"] for match in matches} == {"100", "200"}
        assert all(match["variant_type"] == "alternate" for match in matches)


class TestTitleVariants(unittest.TestCase):

    def test_returns_primary_and_alternate_names(self):
        self.assertEqual(
            get_title_variants("Wingspan", "Flügelschlag | Fesztáv"),
            [
                ("Wingspan", "wingspan", "primary"),
                ("Flügelschlag", "flügelschlag", "alternate"),
                ("Fesztáv", "fesztáv", "alternate"),
            ]
        )

    def test_removes_duplicate_normalized_variants(self):
        self.assertEqual(
            get_title_variants("Pandemic", "PANDEMIC | pandemic"),
            [("Pandemic", "pandemic", "primary")],
        )

    def test_decodes_escaped_alternate_names(self):
        self.assertEqual(
            get_title_variants("Wingspan", r"\u041a\u0440\u044b\u043b\u044c\u044f"),
            [
                ("Wingspan", "wingspan", "primary"),
                ("Крылья", "крылья", "alternate"),
            ]
        )

    def test_deduplicates_punctuation_variants(self):
        result = get_title_variants(
            "A-B",
            "A/B | A B",
        )

        self.assertEqual(
            result,
            [("A-B", "a b", "primary")],
        )

    def test_first_valid_variant_retains_alternate_type(self):
        result = get_title_variants("!!!", "Valid Alternate")

        self.assertEqual(
            result,
            [("Valid Alternate", "valid alternate", "alternate")],
        )


if __name__ == "__main__":
    unittest.main()
