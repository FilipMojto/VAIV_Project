from src.wiki_extraction import extract_wikipedia_game_fields


def test_extracts_publication_history_from_article_section():
    text = """
== Publication ==
* First edition: 1995; 31 years ago<ref>Source 1</ref>
* Second edition: 1996; 30 years ago<ref>Source 2</ref>
* Third edition: 1997; 29 years ago

== Gameplay ==
Some unrelated text.
"""

    result = extract_wikipedia_game_fields(text)

    assert "First edition: 1995" in result["publication_history"]
    assert "Second edition: 1996" in result["publication_history"]
    assert "Third edition: 1997" in result["publication_history"]
    assert "Gameplay" not in result["publication_history"]
    assert "Source 1" not in result["publication_history"]


def test_extracts_short_description_and_infobox_fields():
    text = """
{{Short description|Board game}}
{{Infobox game
| designer = [[Alex Randolph]]
| publisher = [[Milton Bradley]]
| released = 1986
| players = 2–4
| playing time = 60 minutes
| genre = Board game
}}
"""

    result = extract_wikipedia_game_fields(text)

    assert result["short_description"] == "Board game"
    assert result["infobox_type"] == "game"
    assert result["designer"] == "Alex Randolph"
    assert result["publisher"] == "Milton Bradley"
    assert result["release_date"] == "1986"
    assert result["number_of_players"] == "2–4"
    assert result["playing_time"] == "60 minutes"


def test_supports_alternate_release_date_parameter():
    text = """
{{Infobox game
| release date = 1995
}}
"""

    result = extract_wikipedia_game_fields(text)

    assert result["release_date"] == "1995"


def test_missing_fields_are_none():
    result = extract_wikipedia_game_fields("An ordinary article.")

    assert result["short_description"] is None
    assert result["infobox_type"] is None
    assert result["designer"] is None
    assert result["publisher"] is None
    assert result["release_date"] is None
    assert result["number_of_players"] is None
    assert result["playing_time"] is None
    assert result["publication_history"] is None
    assert result["setup_time"] is None
    assert result["chance"] is None
    assert result["official_website"] is None


def test_missing_article_text_returns_empty_fields():
    result = extract_wikipedia_game_fields(None)

    assert all(value is None for value in result.values())


def test_extracts_infobox_parameter_with_nested_template():
    text = """
{{Infobox game
| designer = {{hlist|[[Designer One]]|[[Designer Two]]}}
| publisher = Example Publisher
}}
"""

    result = extract_wikipedia_game_fields(text)

    assert result["designer"] == "Designer One|Designer Two"
    assert result["publisher"] == "Example Publisher"


def test_extracts_additional_game_fields():
    text = """
{{Infobox game
| publication history = First edition 1995; second edition 2001
| setup time = 10 minutes
| random chance = Dice rolling
| website = https://example.com
}}
"""

    result = extract_wikipedia_game_fields(text)

    assert result["publication_history"] == ("First edition 1995; second edition 2001")
    assert result["setup_time"] == "10 minutes"
    assert result["chance"] == "Dice rolling"
    assert result["official_website"] == "https://example.com"
