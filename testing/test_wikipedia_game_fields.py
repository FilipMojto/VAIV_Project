
from src.wiki_extraction import extract_wikipedia_game_fields


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


def test_extracts_release_date_from_nested_date_template():
    text = """
    {{Infobox game
    | date = {{Start date and age|1986}}
    }}
    """

    result = extract_wikipedia_game_fields(text)

    assert result["release_date"] == "1986"
