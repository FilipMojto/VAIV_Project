import csv
from pathlib import Path
import pytest

from src.config import BGG_DIR, BGG_FILE_NAME
from src.crawling import PageHTMLFetcher
from src.parsing import FIELDS_COMPLETE_LIST, parse_html_metadata
from src.utils import verify_file_header
from src.versioning import SmartVersioner

# Priečinok, kde máš uložených 20 testovacích HTML súborov
FIXTURES_DIR = Path("tests/fixtures")


# Zoznam 20 hier a ich očakávaných hodnôt (ground truth)
TEST_CASES = [
    # Klasiky a rodinné hry
    {
        "filename": "game_13.html",
        "app_id": "13",
        "game_title": "Catan",
        "release_year": "1995",
        "game_type": ["Family", "Strategy"],
        "num_of_players_min": "3",
        "num_of_players_max": "4",
        "play_time_min": "60",
        "play_time_max": "120",
        "designer": ["Klaus Teuber"]
    },
    {
        "filename": "game_822.html",
        "app_id": "822",
        "game_title": "Carcassonne",
        "release_year": "2000",
        "game_type": ["Family"],
        "num_of_players_min": "2",
        "num_of_players_max": "5",
        "play_time_min": "30",
        "play_time_max": "45",
        "designer": ["Klaus-Jürgen Wrede"]
    },
    {
        "filename": "game_9209.html",
        "app_id": "9209",
        "game_title": "Ticket to Ride",
        "release_year": "2004",
        "game_type": ["Family"],
        "num_of_players_min": "2",
        "num_of_players_max": "5",
        "play_time_min": "30",
        "play_time_max": "60",
        "designer": ["Alan R. Moon"]
    },
    {
        "filename": "game_39856.html",
        "app_id": "39856",
        "game_title": "Dixit",
        "release_year": "2008",
        "game_type": ["Party"],
        "num_of_players_min": "3",
        "num_of_players_max": "8",
        "play_time_min": "30",
        "play_time_max": "30",
        "designer": ["Jean-Louis Roubira"]
    },
    {
        "filename": "game_148228.html",
        "app_id": "148228",
        "game_title": "Splendor",
        "release_year": "2014",
        "game_type": ["Family"],
        "num_of_players_min": "2",
        "num_of_players_max": "4",
        "play_time_min": "30",
        "play_time_max": "30",
        "designer": ["Marc André"]
        
    },
    {
        "filename": "game_230802.html",
        "app_id": "230802",
        "game_title": "Azul",
        "release_year": "2017",
        "game_type": ["Abract", "Family"],
        "num_of_players_min": "2",
        "num_of_players_max": "4",
        "play_time_min": "30",
        "play_time_max": "45",
        "designer": ["Michael Kiesling"]
    },
    {
        "filename": "game_178900.html",
        "app_id": "178900",
        "game_title": "Codenames",
        "release_year": "2015",
        "game_type": ["Party"],
        "num_of_players_min": "2",
        "num_of_players_max": "8",
        "play_time_min": "15",
        "play_time_max": "15",
        "designer": ["Vlaada Chvátil"]
    },
    {
        "filename": "game_68448.html",
        "app_id": "68448",
        "game_title": "7 Wonders",
        "release_year": "2010",
        "game_type": ["Family", "Strategy"],
        "num_of_players_min": "2",
        "num_of_players_max": "7",
        "play_time_min": "30",
        "play_time_max": "30",
        "designer": ["Antoine Bauza"]
    },
    {
        "filename": "game_173346.html",
        "app_id": "173346",
        "game_title": "7 Wonders Duel",
        "release_year": "2015",
        "game_type": ["Strategy"],
        "num_of_players_min": "2",
        "num_of_players_max": "2",
        "play_time_min": "30",
        "play_time_max": "30",
        "designer": ["Antoine Bauza", "Bruno Cathala"]
    },
    {
        "filename": "game_284083.html",
        "app_id": "284083",
        "game_title": "The Crew: The Quest for Planet Nine",
        "release_year": "2019",
        "game_type": ["Family"],
        "num_of_players_min": "2",
        "num_of_players_max": "5",
        "play_time_min": "20",
        "play_time_max": "20",
        "designer": "Thomas Sing"
    },

    # Kooperatívne a tematické hry
    {
        "filename": "game_30549.html",
        "app_id": "30549",
        "game_title": "Pandemic",
        "release_year": "2008",
        "game_type": ["Family", "Strategy"],
        "num_of_players_min": "2",
        "num_of_players_max": "4",
        "play_time_min": "45",
        "play_time_max": "45",
        "designer": "Matt Leacock"
    },
    {
        "filename": "game_162886.html",
        "app_id": "162886",
        "game_title": "Spirit Island",
        "release_year": "2017",
        "game_type": ["Strategy"],
        "num_of_players_min": "1",
        "num_of_players_max": "4",
        "play_time_min": "90",
        "play_time_max": "120",
        "designer": ["R. Eric Reuss"]
    },
    {
        "filename": "game_174430.html",
        "app_id": "174430",
        "game_title": "Gloomhaven",
        "release_year": "2017",
        "game_type": ["Strategy", "Thematic"],
        "num_of_players_min": "1",
        "num_of_players_max": "4",
        "play_time_min": "60",
        "play_time_max": "120",
        "designer": ["Isaac Childres"]
    },
    {
        "filename": "game_237182.html",
        "app_id": "237182",
        "game_title": "Root",
        "release_year": "2018",
        "game_type": ["Strategy", "Wargames"],
        "num_of_players_min": "2",
        "num_of_players_max": "4",
        "play_time_min": "60",
        "play_time_max": "90",
        "designer": ["Cole Wehrle"]
    },
    {
        "filename": "game_266192.html",
        "app_id": "266192",
        "game_title": "Wingspan",
        "release_year": "2019",
        "game_type": ["Family", "Strategy"],
        "num_of_players_min": "1",
        "num_of_players_max": "5",
        "play_time_min": "40",
        "play_time_max": "70",
        "designer": ["Elizabeth Hargrave"]
    },

    # Ekonomické a strategické hry
    {
        "filename": "game_36218.html",
        "app_id": "36218",
        "game_title": "Dominion",
        "release_year": "2008",
        "game_type": ["Strategy"],
        "num_of_players_min": "2",
        "num_of_players_max": "4",
        "play_time_min": "30",
        "play_time_max": "30",
        "designer": ["Donald X. Vaccarino"]
    },
    {
        "filename": "game_31260.html",
        "app_id": "31260",
        "game_title": "Agricola",
        "release_year": "2007",
        "game_type": ["Strategy"],
        "num_of_players_min": "1",
        "num_of_players_max": "5",
        "play_time_min": "30",
        "play_time_max": "150",
        "designer": ["Uwe Rosenberg"]
    },
    {
        "filename": "game_3076.html",
        "app_id": "3076",
        "game_title": "Puerto Rico",
        "release_year": "2002",
        "game_type": ["Strategy"],
        "num_of_players_min": "3",
        "num_of_players_max": "5",
        "play_time_min": "90",
        "play_time_max": "150",
        "designer": ["Franz Vohwinkel"]
    },
    {
        "filename": "game_12333.html",
        "app_id": "12333",
        "game_title": "Twilight Struggle",
        "release_year": "2005",
        "game_type": ["Strategy", "Wargames"],
        "num_of_players_min": "2",
        "num_of_players_max": "",
        "play_time_min": "120",
        "play_time_max": "180",
        "designer": ["Ananda Gupta, Jason Matthews"]
    },
    {
        "filename": "game_167791.html",
        "app_id": "167791",
        "game_title": "Terraforming Mars",
        "release_year": "2016",
        "game_type": ["Strategy"],
        "num_of_players_min": "1",
        "num_of_players_max": "5",
        "play_time_min": "120",
        "play_time_max": "120",
        "designer": ["Jacob Fryxelius"]
    },
    {
        "filename": "game_224517.html",
        "app_id": "224517",
        "game_title": "Brass: Birmingham",
        "release_year": "2018",
        "game_type": ["Strategy"],
        "num_of_players_min": "2",
        "num_of_players_max": "4",
        "play_time_min": "60",
        "play_time_max": "120",
        "designer": ["Gavan Brown", "Matt Tolman", "Martin Wallace"]
    },
    {
        "filename": "game_342942.html",
        "app_id": "342942",
        "game_title": "Ark Nova",
        "release_year": "2021",
        "game_type": ["Strategy"],
        "num_of_players_min": "1",
        "num_of_players_max": "4",
        "play_time_min": "90",
        "play_time_max": "150",
        "designer": ["Mathias Wigge"]
    },
    {
        "filename": "game_182028.html",
        "app_id": "182028",
        "game_title": "Through the Ages: A New Story of Civilization",
        "release_year": "2015",
        "game_type": ["Strategy"],
        "num_of_players_min": "2",
        "num_of_players_max": "4",
        "play_time_min": "120",
        "play_time_max": "120",
        "designer": ["Vlaada Chvátil"]
    },

    # Klasická abstraktná hra
    {
        "filename": "game_171.html",
        "app_id": "171",
        "game_title": "Chess",
        "release_year": "1475",
        "game_type": ["Abtract"],
        "num_of_players_min": "2",
        "num_of_players_max": "2",
        "play_time_min": "",
        "play_time_max": "",
        "designer": "(Uncredited)"
    },
]


@pytest.mark.parametrize("case", TEST_CASES)
def test_regex_parser_with_fixtures(case):
    with PageHTMLFetcher(log_func=print) as page_fetcher:
        html_content = page_fetcher.get_html(page_id=case["app_id"])
        extracted_data = parse_html_metadata(html_content=html_content, page_id=case['app_id'])

        # Spustenie tvojho regex extraktora / parsera
        # parser = BGGParser(html_content)
        # extracted_data = parser.parse()  # vracia slovník extrahovaných atribútov

        # Overenie assertionov
        # 3. Dynamické overenie všetkých kľúčov, ktoré sú definované v test case
        for key, expected_value in case.items():
            if key == "filename":
                continue  # preskočíme názov súboru

            actual_value = extracted_data.get(key)

            # Assert s detailnou chybovou hláškou, ak niečo nesedí
            assert (
                actual_value == expected_value
            ), f"Chyba v súbore {case['filename']} pre atribút '{key}': očakávané '{expected_value}', ale parser našiel '{actual_value}'"
        # assert (
        #     extracted_data.get("app_id") == case["app_id"]
        # ), f"Nesedí ID pre {case['filename']}"
        # assert (
        #     extracted_data.get("game_title") == case["game_title"]
        # ), f"Nesedí názov pre {case['filename']}"
        # assert (
        #     extracted_data.get("release_year") == case["release_year"]
        # ), f"Nesedí rok pre {case['filename']}"
