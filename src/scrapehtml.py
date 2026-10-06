import os
import re
import time
import csv
import json
from pathlib import Path
from argparse import ArgumentParser
from playwright.sync_api import sync_playwright
from tqdm import tqdm

from src.config import BGG_GAMES_DIR, DATA_DIR, HARVEST_FILE_NAME
from src.versioning import SmartVersioner
from src.config import CDP_URL
from src.parsing import parse_descriptions, parse_game_credits, parse_game_metrics
from src.parsing import parse_game_ranks, parse_general_fields, parse_general_stats
from src.parsing import parse_player_plays_stats, parse_player_stats, parse_ratings_and_awards
from src.parsing import parse_relationship_fields
from src.parsing import parsing_mappings

# --- CONFIGURATION ---
OUTPUT_DIR = DATA_DIR / "bgg_raw_htmls"
OUTPUT_TSV = BGG_GAMES_DIR / "bgg_games.tsv"

os.makedirs(OUTPUT_DIR, exist_ok=True)

parser = ArgumentParser(
    description="Scrape and parse BGG game metadata from raw HTML files via Playwright CDP."
)
parser.add_argument(
    "--input",
    type=Path,
    default=HARVEST_FILE_NAME,
    help=f"Path to the input file containing BGG app IDs. Default: {HARVEST_FILE_NAME}",
)
parser.add_argument(
    "--smart_append",
    action="store_true",
    help="Enable smart appending to resume from the last checkpoint.",
)
parser.add_argument(
    "--reparse_fields",
    action="store_true",
    help="Reparse every specified field and apply its every transformation(s) from cached HTML.",
)
# parser.add_argument(
#     "--backfill_missing",
#     action="store_true",
#     help="Re-parse cached HTML for existing rows with blank fields (also enables smart append).",
# )
# parser.add_argument(
#     "--enforce_types",
#     action="store_true",
#     help="Reparse every existing field from cached HTML and apply current conversions.",
# )
# parser.add_argument(
#     "--reparse_field",
#     help="Reparse one field for every existing row using cached HTML; --enforce_types reparses all fields.",
# )
args = parser.parse_args()




def zero_as_none(value: str) -> str:
    """Convert a string representing a number to None if it is zero or empty."""
    if not value or value == "0":
        return None
    return value


def parse_game_html(app_id: str, html_content: str) -> dict:
    """Extracts game metadata using Regular Expressions from rendered BGG HTML."""
    game_data = {"app_id": app_id}

    for group_name, parser in parsing_mappings.items():
        try:
            # Call the parser function directly
            parsed_dict = parser(html_content)
            
            # Ensure the parser returned a valid dictionary before updating
            if isinstance(parsed_dict, dict):
                game_data.update(parsed_dict)
            else:
                print(f"[WARNING] Parser '{group_name}' for game {app_id} did not return a dict.")

        except Exception as e:
            # Log the specific parser failure without halting the extraction for this game
            print(f"[ERROR] Parsing failed for group '{group_name}' on game {app_id}: {e}")

    # --- general fields ---
    game_data.update(parse_general_fields(html_content))

    # # ZÁKLADNÉ METADÁTA (Príklady Regexov pre BGG)
    # # Názov a rok sa často nachádzajú v title alebo v hlavičke
    # title_match = re.search(
    #     r'<meta property="og:title" content="(.*?)(?:\s\(\d{4}\))?"', html_content
    # )
    # game_data["game_title"] = (
    #     clean_html_text(title_match.group(1)) if title_match else ""
    # )

    # year_match = re.search(
    #     r'<span[^>]*class="game-year"[^>]*>\s*\(\s*(\d+)\s*\)\s*</span>', html_content
    # )
    # game_data["release_year"] = year_match.group(1) if year_match else ""

    
    # --- descriptions ---
    game_data.update(parse_descriptions(html_content))

    # desc_match = re.search(r'<meta name="description" content="(.*?)"', html_content)
    # game_data["short_description"] = (
    #     clean_html_text(desc_match.group(1)) if desc_match else ""
    # )
    
    # --- game_metrics ---
    game_data.update(parse_game_metrics(html_content))
    # --- Average Rating & Awards ---
    game_data.update(parse_ratings_and_awards(html_content))
    # rating_targets = [
    #     (
    #         "avg_rating",
    #         "Avg. Rating",
    #         ["averagerating", "avg_rating", "rating", "average"],
    #     )
    # ]

    # for field_name, dom_title, json_keys in rating_targets:
    #     dom_value = ""
    #     item_pattern = (
    #         r'<li\b[^>]*class=["\'][^"\']*\boutline-item\b[^"\']*["\'][^>]*>(.*?)</li>'
    #     )

    #     for item_match in re.finditer(
    #         item_pattern, html_content, re.IGNORECASE | re.DOTALL
    #     ):
    #         item_html = item_match.group(1)

    #         # Match the title container
    #         title_match = re.search(
    #             r'<div\b[^>]*class=["\'][^"\']*\boutline-item-title\b[^"\']*["\'][^>]*>(.*?)</div>',
    #             item_html,
    #             re.IGNORECASE | re.DOTALL,
    #         )
    #         if not title_match:
    #             continue

    #         title_text = clean_html_text(title_match.group(1)).casefold()
    #         if dom_title.casefold() not in title_text:
    #             continue

    #         # Match the description container
    #         description_match = re.search(
    #             r'<div\b[^>]*class=["\'][^"\']*\boutline-item-description\b[^"\']*["\'][^>]*>(.*?)</div>',
    #             item_html,
    #             re.IGNORECASE | re.DOTALL,
    #         )
    #         if description_match:
    #             desc_html = description_match.group(1)

    #             # Extract from the anchor tag
    #             value_match = re.search(
    #                 r"<a\b[^>]*>(.*?)</a>", desc_html, re.IGNORECASE | re.DOTALL
    #             )
    #             if value_match:
    #                 raw_val = clean_html_text(value_match.group(1))
    #                 # Keep digits AND the decimal point (e.g., "8.130" remains "8.130")
    #                 dom_value = re.sub(r"[^\d.]", "", raw_val)
    #         break

    #     if dom_value:
    #         game_data[field_name] = dom_value
    #         continue

    #     # JSON Fallback (Floating-point safe matching)
    #     found_val = ""
    #     for key in json_keys:
    #         json_match = re.search(
    #             rf'"{key}"\s*:\s*"?([\d.]+)"?', html_content, re.IGNORECASE
    #         )
    #         if json_match:
    #             found_val = json_match.group(1)
    #             break
    #     game_data[field_name] = found_val

    # --- num_of_players ---
    # game_data.update(parse_num_of_players(html_content))

    # # Extrakcia minimálneho a maximálneho počtu hráčov z <meta> tagov
    # min_match = re.search(
    #     r'<meta[^>]*itemprop="minValue"[^>]*content="(\d+)"', html_content
    # )
    # max_match = re.search(
    #     r'<meta[^>]*itemprop="maxValue"[^>]*content="(\d+)"', html_content
    # )

    # min_players = min_match.group(1) if min_match else ""
    # max_players = max_match.group(1) if max_match else ""

    # # Formátovanie výstupu (napr. "1–4" alebo "1" ak sa min a max rovnajú)
    # if min_players and max_players:
    #     if min_players == max_players:
    #         game_data["num_of_players"] = min_players
    #     else:
    #         game_data["num_of_players"] = f"{min_players}–{max_players}"
    # elif min_players or max_players:
    #     game_data["num_of_players"] = min_players or max_players
    # else:
    #     game_data["num_of_players"] = ""

    # --- playing_time ---
    game_data.update(parse_player_plays_stats(html_content))
    # min_time_match = re.search(
    #     r'<meta[^>]*itemprop="minplaytime"[^>]*content="(\d+)"',
    #     html_content,
    #     re.IGNORECASE,
    # )
    # max_time_match = re.search(
    #     r'<meta[^>]*itemprop="maxplaytime"[^>]*content="(\d+)"',
    #     html_content,
    #     re.IGNORECASE,
    # )

    # # Fallback regex in case meta tags are structured inside Angular JSON
    # if not min_time_match:
    #     min_time_match = re.search(r'"minplaytime"\s*:\s*"?(\d+)"?', html_content)
    # if not max_time_match:
    #     max_time_match = re.search(r'"maxplaytime"\s*:\s*"?(\d+)"?', html_content)

    # min_time = min_time_match.group(1) if min_time_match else ""
    # max_time = max_time_match.group(1) if max_time_match else ""

    # game_data["play_time_min"] = min_time
    # game_data["play_time_max"] = max_time

    # --- weight ---
    # game_data.update(parse_weight(html_content))
    # # Extrakcia náročnosti / váhy hry (weight)
    # weight_match = re.search(
    #     r'<span[^>]*item-poll-button="boardgameweight"[^>]*>(.*?)</span>',
    #     html_content,
    #     re.DOTALL,
    # )

    # if weight_match:
    #     raw_weight = clean_html_text(weight_match.group(1))
    #     # Zachytí desatinné číslo (napr. "2.34" z textu "2.34 / 5")
    #     num_match = re.search(r"(\d+(?:\.\d+)?)", raw_weight)
    #     game_data["weight"] = num_match.group(1) if num_match else ""
    # else:
    #     # Záložný regex pre raw HTML (údaje v vstavanom JSON objekte BGG)
    #     json_weight = re.search(
    #         r'"averageweight"\s*:\s*"?(\d+(?:\.\d+)?)"?', html_content
    #     )
    #     game_data["weight"] = json_weight.group(1) if json_weight else ""

    # --- general_stats ---
    game_data.update(parse_general_stats(html_content))


    # --- age ---
    # # Extract minimum age
    # age_match = re.search(
    #     r'<span[^>]*itemprop="suggestedMinAge"[^>]*>\s*(\d+)\s*</span>', html_content
    # )

    # # Fallback in case raw JSON data is matched
    # if not age_match:
    #     age_match = re.search(r'"minage"\s*:\s*"?(\d+)"?', html_content)

    # game_data["age"] = f"{age_match.group(1)}+" if age_match else ""
    # # --- alternate_names ---
    # game_data.update(parse_alternate_names(html_content))
    # # Extract all alternate names from the page
    # alt_names_matches = re.findall(
    #     r'<div[^>]*ng-switch-when="alternatename"[^>]*>\s*(.*?)\s*</div>',
    #     html_content,
    #     re.DOTALL,
    # )

    # if alt_names_matches:
    #     # Clean text and filter out empty strings
    #     cleaned_names = [
    #         clean_html_text(name) for name in alt_names_matches if clean_html_text(name)
    #     ]

    #     # Remove duplicates while preserving original order
    #     unique_names = list(dict.fromkeys(cleaned_names))

    #     # Join with pipe separator so commas inside titles won't disrupt parsing
    #     game_data["alternate_names"] = " | ".join(unique_names)
    # else:
    #     # Fallback regex for embedded JSON data in the HTML source
    #     json_alt_matches = re.findall(
    #         r'"alternatenames"\s*:\s*\[(.*?)\]', html_content, re.DOTALL
    #     )
    #     if json_alt_matches:
    #         names_in_json = re.findall(r'"name"\s*:\s*"([^"]+)"', json_alt_matches[0])
    #         game_data["alternate_names"] = " | ".join(dict.fromkeys(names_in_json))
    #     else:
    #         game_data["alternate_names"] = ""

    # --- game_credits ---
    game_data.update(parse_game_credits(html_content))

    # # --- designer ---
    # # Extract all designers
    # designer_matches = re.findall(
    #     r'<a[^>]*href="[^"]*/boardgamedesigner/\d+/[^"]*"[^>]*>\s*(.*?)\s*</a>',
    #     html_content,
    #     re.DOTALL,
    # )

    # if designer_matches:
    #     # Clean HTML text for each designer name
    #     cleaned_designers = [
    #         clean_html_text(d) for d in designer_matches if clean_html_text(d)
    #     ]

    #     # Deduplicate while preserving order
    #     unique_designers = list(dict.fromkeys(cleaned_designers))

    #     # Join multiple designers with a comma (e.g., "Bruno Cathala, Antoine Bauza")
    #     game_data["designer"] = ", ".join(unique_designers)
    # else:
    #     # Fallback for embedded JSON data in raw HTML
    #     json_designers = re.findall(
    #         r'"boardgamedesigner"\s*:\s*\[(.*?)\]', html_content, re.DOTALL
    #     )
    #     if json_designers:
    #         names = re.findall(r'"name"\s*:\s*"([^"]+)"', json_designers[0])
    #         game_data["designer"] = ", ".join(dict.fromkeys(names))
    #     else:
    #         game_data["designer"] = ""
  
    # # --- artist ---
    # # Extract all artists
    # artist_matches = re.findall(
    #     r'<a[^>]*href="[^"]*/boardgameartist/\d+/[^"]*"[^>]*>\s*(.*?)\s*</a>',
    #     html_content,
    #     re.DOTALL,
    # )

    # if artist_matches:
    #     # Clean HTML text for each artist name
    #     cleaned_artists = [
    #         clean_html_text(a) for a in artist_matches if clean_html_text(a)
    #     ]

    #     # Deduplicate while preserving order
    #     unique_artists = list(dict.fromkeys(cleaned_artists))

    #     # Join multiple artists with a comma
    #     game_data["artist"] = ", ".join(unique_artists)
    # else:
    #     # Fallback for embedded JSON data in raw HTML
    #     json_artists = re.findall(
    #         r'"boardgameartist"\s*:\s*\[(.*?)\]', html_content, re.DOTALL
    #     )
    #     if json_artists:
    #         names = re.findall(r'"name"\s*:\s*"([^"]+)"', json_artists[0])
    #         game_data["artist"] = ", ".join(dict.fromkeys(names))
    #     else:
    #         game_data["artist"] = ""

    # # --- publisher ---
    # # Extract all publishers by strictly matching text inside the anchor tags
    # # Skip the DOM entirely to bypass lazy-loading truncation
    # # Target the complete list stored in BGG's embedded JSON object
    # json_block = re.search(
    #     r'"boardgamepublisher"\s*:\s*\[(.*?)\]', html_content, re.DOTALL
    # )

    # publishers = []
    # if json_block:
    #     # Extract all "name" values from the matched JSON array
    #     json_names = re.findall(r'"name"\s*:\s*"([^"]+)"', json_block.group(1))

    #     for name in json_names:
    #         # Decode unicode characters (e.g., converting "Lookout\u0020Games" to "Lookout Games")
    #         decoded_name = bytes(name, "utf-8").decode("unicode_escape")
    #         if decoded_name not in publishers:
    #             publishers.append(decoded_name)

    # # Join unique publishers with a pipe separator
    # game_data["publisher"] = " | ".join(publishers)

    # --- description ---

    # # Extract the full game description
    # desc_match = re.search(
    #     r'<article class="game-description-body"[^>]*>(.*?)</article>',
    #     html_content,
    #     re.DOTALL,
    # )

    # if desc_match:
    #     raw_desc = desc_match.group(1)

    #     # Strip all inner HTML tags (e.g., <p>, <em>, <br>) and replace with spaces
    #     no_tags_desc = re.sub(r"<[^>]+>", " ", raw_desc)

    #     # Normalize spaces and strip newlines to ensure single-line TSV compatibility
    #     game_data["description"] = clean_html_text(no_tags_desc)
    # else:
    #     # Fallback to BGG's embedded JSON object
    #     json_desc = re.search(
    #         r'"description"\s*:\s*"(.*?)(?<!\\)"', html_content, re.DOTALL
    #     )
    #     if json_desc:
    #         raw_json_desc = json_desc.group(1)
    #         # Decode JSON unicode escapes (e.g., \u0027 for apostrophes) and newlines (\n)
    #         decoded_desc = bytes(raw_json_desc, "utf-8").decode("unicode_escape")
    #         no_tags_json = re.sub(r"<[^>]+>", " ", decoded_desc)
    #         game_data["description"] = clean_html_text(no_tags_json)
    #     else:
    #         game_data["description"] = ""

    # # --- awards_honors ---
    # # Extract all awards and honors by strictly matching text inside the anchor tags
    # award_matches = re.findall(
    #     r'<a[^>]*href="[^"]*/boardgamehonor/\d+/[^"]*"[^>]*>\s*([^<]+?)\s*</a>',
    #     html_content,
    # )

    # awards = []
    # if award_matches:
    #     for a in award_matches:
    #         clean_name = clean_html_text(a)
    #         if clean_name and clean_name not in awards:
    #             awards.append(clean_name)

    # # Fallback to BGG's embedded JSON object in case DOM rendering is incomplete
    # if not awards or len(awards) <= 2:
    #     json_block = re.search(
    #         r'"boardgamehonor"\s*:\s*\[(.*?)\]', html_content, re.DOTALL
    #     )
    #     if json_block:
    #         # Match JSON strings including escaped quotes and backslashes. The
    #         # unicode_escape codec rejects valid names ending in a backslash
    #         # and can corrupt non-ASCII text; let the JSON decoder handle them.
    #         json_names = re.findall(
    #             r'"name"\s*:\s*("(?:\\.|[^"\\])*")', json_block.group(1)
    #         )
    #         for encoded_name in json_names:
    #             try:
    #                 decoded_name = json.loads(encoded_name)
    #             except json.JSONDecodeError:
    #                 # Preserve the extracted text if the embedded page data is
    #                 # malformed, rather than aborting the entire game scrape.
    #                 decoded_name = encoded_name[1:-1]
    #             decoded_name = clean_html_text(decoded_name)
    #             if decoded_name not in awards:
    #                 awards.append(decoded_name)

    # # Join unique awards with a pipe separator (awards often contain commas)
    # game_data["awards_honors"] = " | ".join(awards)

    # --- player_stats ---
    game_data.update(parse_player_stats(html_content))
    # # Map each field to its clean search token and expanded JSON keys
    # # Map each field to its exact DOM title and potential JSON fallback keys
    # # Unified stat extraction bypassing all HTML attributes
    # stat_targets = [
    #     ("own", "Own", ["numowned", "owned"]),
    #     ("prev_owned", "Prev. Owned", ["numprevowned", "prevowned"]),
    #     ("for_trade", "For Trade", ["numfortrade", "fortrade"]),
    #     ("want_in_trade", "Want In Trade", ["numwanting", "wanting", "numwant"]),
    #     (
    #         "wishlist",
    #         "Wishlist",
    #         ["numwishing", "wishing", "wishlist", "numwishlist", "numwish"],
    #     ),
    #     ("has_parts", "Has Parts", ["numhasparts", "hasparts"]),
    #     (
    #         "wants_parts",
    #         "Want Parts",
    #         ["numwantparts", "wantparts", "numwantingparts", "wantingparts"],
    #     ),
    # ]

    # for field_name, dom_title, json_keys in stat_targets:
    #     # Each statistic is an outline-item with a title and a separate
    #     # description. Match within that item so title-side links (such as
    #     # "Find For Trade Matches") cannot be mistaken for the count.
    #     dom_value = ""
    #     item_pattern = (
    #         r'<li\b[^>]*class=["\'][^"\']*\boutline-item\b[^"\']*["\'][^>]*>(.*?)</li>'
    #     )
    #     for item_match in re.finditer(
    #         item_pattern, html_content, re.IGNORECASE | re.DOTALL
    #     ):
    #         item_html = item_match.group(1)
    #         title_match = re.search(
    #             r'<div\b[^>]*class=["\'][^"\']*\boutline-item-title\b[^"\']*["\'][^>]*>(.*?)</div>',
    #             item_html,
    #             re.IGNORECASE | re.DOTALL,
    #         )
    #         if not title_match:
    #             continue

    #         title_text = clean_html_text(title_match.group(1)).casefold()
    #         if not re.match(rf"^{re.escape(dom_title.casefold())}\s*:", title_text):
    #             continue

    #         description_match = re.search(
    #             r'<div\b[^>]*class=["\'][^"\']*\boutline-item-description\b[^"\']*["\'][^>]*>(.*?)</div>',
    #             item_html,
    #             re.IGNORECASE | re.DOTALL,
    #         )
    #         if description_match:
    #             value_match = re.search(
    #                 r"<a\b[^>]*>(.*?)</a>",
    #                 description_match.group(1),
    #                 re.IGNORECASE | re.DOTALL,
    #             )
    #             if value_match:
    #                 dom_value = re.sub(
    #                     r"[^\d]", "", clean_html_text(value_match.group(1))
    #                 )
    #         break

    #     # BGG displays "--" for unranked categories but embeds those as rank 0.
    #     # Keep unspecified ranks blank so they pass the non-negative rank check.
    #     if dom_value and int(dom_value) > 0:
    #         game_data[field_name] = dom_value
    #         continue

    #     # JSON Fallback (Runs only if the DOM block is entirely missing)
    #     found_val = ""
    #     for key in json_keys:
    #         json_match = re.search(
    #             rf'"{key}"\s*:\s*"?(\d+)"?', html_content, re.IGNORECASE
    #         )
    #         if json_match:
    #             found_val = json_match.group(1)
    #             break
    #     game_data[field_name] = found_val if found_val and int(found_val) > 0 else ""

    # --- Comments, Fans, and Page Views ---
    # stat_targets = [
    #     ("comments", "Comments", ["numcomments", "comments"]),
    #     ("fans", "Fans", ["numfans", "fans"]),
    #     (
    #         "page_views",
    #         "Page Views",
    #         ["numpageviews", "pageviews", "views", "numviews"],
    #     ),
    # ]

    # for field_name, dom_title, json_keys in stat_targets:
    #     dom_value = ""
    #     item_pattern = (
    #         r'<li\b[^>]*class=["\'][^"\']*\boutline-item\b[^"\']*["\'][^>]*>(.*?)</li>'
    #     )

    #     for item_match in re.finditer(
    #         item_pattern, html_content, re.IGNORECASE | re.DOTALL
    #     ):
    #         item_html = item_match.group(1)

    #         # Match the title container
    #         title_match = re.search(
    #             r'<div\b[^>]*class=["\'][^"\']*\boutline-item-title\b[^"\']*["\'][^>]*>(.*?)</div>',
    #             item_html,
    #             re.IGNORECASE | re.DOTALL,
    #         )
    #         if not title_match:
    #             continue

    #         title_text = clean_html_text(title_match.group(1)).casefold()
    #         # Use exact or clean inclusion match since titles like "Comments" do not have a colon
    #         if dom_title.casefold() not in title_text:
    #             continue

    #         # Match the description container
    #         description_match = re.search(
    #             r'<div\b[^>]*class=["\'][^"\']*\boutline-item-description\b[^"\']*["\'][^>]*>(.*?)</div>',
    #             item_html,
    #             re.IGNORECASE | re.DOTALL,
    #         )
    #         if description_match:
    #             desc_html = description_match.group(1)

    #             # 1. Try extracting from an <a> tag first (Comments, Fans)
    #             value_match = re.search(
    #                 r"<a\b[^>]*>(.*?)</a>", desc_html, re.IGNORECASE | re.DOTALL
    #             )
    #             if value_match:
    #                 raw_val = value_match.group(1)
    #             else:
    #                 # 2. Fallback to raw text inside description if no <a> tag exists (Page Views)
    #                 raw_val = desc_html

    #             dom_value = re.sub(r"[^\d]", "", clean_html_text(raw_val))
    #         break

    #     if dom_value:
    #         game_data[field_name] = dom_value
    #         continue

    #     # JSON Fallback (Runs only if the DOM block is missing)
    #     found_val = ""
    #     for key in json_keys:
    #         json_match = re.search(
    #             rf'"{key}"\s*:\s*"?(\d+)"?', html_content, re.IGNORECASE
    #         )
    #         if json_match:
    #             found_val = json_match.group(1)
    #             break
    #     game_data[field_name] = found_val

    # --- game ranks ---
    game_data.update(parse_game_ranks(html_content))
    # rank_targets = [
    #     ("overall_rank", "Overall Rank", ["Board Game Rank", "Overall Rank"]),
    #     ("strategy_rank", "Strategy Rank", ["Strategy Rank", "Strategy Game Rank"]),
    #     ("party_rank", "Party Rank", ["Party Game Rank", "Party Rank"]),
    #     ("family_rank", "Family Rank", ["Family Game Rank", "Family Rank"]),
    # ]   

    # # BGG embeds ranks in rankinfo objects, e.g.:
    # # {"shortprettyname":"Strategy Rank", "rank":"55", ...}
    # rankinfo_match = re.search(
    #     r'"rankinfo"\s*:\s*\[(.*?)\]', html_content, re.IGNORECASE | re.DOTALL
    # )
    # rankinfo_entries = []
    # if rankinfo_match:
    #     rankinfo_entries = re.findall(r"\{(.*?)\}", rankinfo_match.group(1), re.DOTALL)

    # for field_name, dom_title, json_keys in rank_targets:
    #     dom_value = ""
    #     item_pattern = (
    #         r'<li\b[^>]*class=["\'][^"\']*\boutline-item\b[^"\']*["\'][^>]*>(.*?)</li>'
    #     )

    #     for item_match in re.finditer(
    #         item_pattern, html_content, re.IGNORECASE | re.DOTALL
    #     ):
    #         item_html = item_match.group(1)

    #         # Match the title container
    #         title_match = re.search(
    #             r'<div\b[^>]*class=["\'][^"\']*\boutline-item-title\b[^"\']*["\'][^>]*>(.*?)</div>',
    #             item_html,
    #             re.IGNORECASE | re.DOTALL,
    #         )
    #         if not title_match:
    #             continue

    #         title_text = clean_html_text(title_match.group(1)).casefold()
    #         if not title_text.startswith(dom_title.casefold()):
    #             continue

    #         # Match the description container
    #         description_match = re.search(
    #             r'<div\b[^>]*class=["\'][^"\']*\boutline-item-description\b[^"\']*["\'][^>]*>(.*?)</div>',
    #             item_html,
    #             re.IGNORECASE | re.DOTALL,
    #         )
    #         if description_match:
    #             desc_html = description_match.group(1)

    #             # Extract from the rank anchor tag (which carries class="rank-value")
    #             value_match = re.search(
    #                 r"<a\b[^>]*>(.*?)</a>", desc_html, re.IGNORECASE | re.DOTALL
    #             )
    #             if value_match:
    #                 dom_value = re.sub(
    #                     r"[^\d]", "", clean_html_text(value_match.group(1))
    #                 )
    #         break

    #     if dom_value:
    #         game_data[field_name] = dom_value
    #         continue

    #     # Match the rankinfo entry by its display name, not by a synthetic
    #     # key such as "strategyrank" (which BGG does not provide).
    #     found_val = ""
    #     for entry in rankinfo_entries:
    #         name_match = re.search(
    #             r'"(?:shortprettyname|prettyname)"\s*:\s*"((?:\\.|[^"\\])*)"',
    #             entry,
    #             re.IGNORECASE,
    #         )
    #         value_match = re.search(r'"rank"\s*:\s*"?(\d+)"?', entry, re.IGNORECASE)
    #         if (
    #             name_match
    #             and value_match
    #             and name_match.group(1).casefold() in [n.casefold() for n in json_keys]
    #         ):
    #             found_val = value_match.group(1)
    #             break

    #     # Retain compatibility with older cached pages that expose direct keys.
    #     if not found_val:
    #         legacy_keys = {
    #             "overall_rank": ["overallrank", "rank"],
    #             "strategy_rank": ["strategyrank"],
    #             "party_rank": ["partyrank"],
    #             "family_rank": ["familyrank"],
    #         }[field_name]
    #         for key in legacy_keys:
    #             json_match = re.search(
    #                 rf'"{key}"\s*:\s*"?(\d+)"?', html_content, re.IGNORECASE
    #             )
    #             if json_match:
    #                 found_val = json_match.group(1)
    #                 break
    #     game_data[field_name] = found_val

    # These play metrics (All Time Plays and This Month) follow the exact same clean outline-item structural pattern you perfected for your main stats loop. Both values are securely wrapped inside standard anchor tags (<a>) within their respective description blocks.   Here is the integration code for both play statistics:Python# --- Play Statistics ---
    # --- All Time Plays and This Month ---
    # --- Play Statistics ---
    game_data.update(parse_player_plays_stats(html_content))

    # classification_targets = [
    #     (
    #         "game_type",
    #         "Type",
    #         ["boardgamesubdomain", "subdomain", "type", "boardgametype"],
    #     ),
    #     (
    #         "game_category",
    #         "Category",
    #         ["boardgamecategory", "category", "boardgamecategories"],
    #     ),
    #     (
    #         "game_mechanic",
    #         "Mechanism",
    #         ["boardgamemechanic", "mechanic", "boardgamemechanics", "mechanics"],
    #     ),
    #     ("game_family", "Family", ["boardgamefamily", "family", "boardgamefamilies"]),
    # ]

    # for field_name, dom_title, json_keys in classification_targets:
    #     dom_values = []

    #     # BGG classification fields use 'feature' blocks or 'outline-item' wrappers
    #     item_pattern = r'<(?:li|div)\b[^>]*class=["\'][^"\']*\b(?:outline-item|feature)\b[^"\']*["\'][^>]*>(.*?)<\/(?:li|div)>'

    #     for item_match in re.finditer(
    #         item_pattern, html_content, re.IGNORECASE | re.DOTALL
    #     ):
    #         item_html = item_match.group(1)

    #         # Match the title container (.outline-item-title or .feature-title)
    #         title_match = re.search(
    #             r'<(?:div|h4)\b[^>]*class=["\'][^"\']*\b(?:outline-item-title|feature-title)\b[^"\']*["\'][^>]*>(.*?)<\/(?:div|h4)>',
    #             item_html,
    #             re.IGNORECASE | re.DOTALL,
    #         )
    #         if not title_match:
    #             continue

    #         title_text = clean_html_text(title_match.group(1)).casefold()
    #         if dom_title.casefold() not in title_text:
    #             continue

    #         # Match the description container (.outline-item-description or .feature-description)
    #         desc_pattern = r'<(?:div|span)\b[^>]*class=["\'][^"\']*\b(?:outline-item-description|feature-description)\b[^"\']*["\'][^>]*>(.*?)<\/(?:div|span)>'
    #         description_match = re.search(
    #             desc_pattern, item_html, re.IGNORECASE | re.DOTALL
    #         )

    #         if description_match:
    #             desc_html = description_match.group(1)

    #             # Extract all anchor tags containing classification labels (e.g., "Creatures: Monsters", "Crowdfunding: Kickstarter")
    #             value_matches = re.findall(
    #                 r"<a\b[^>]*>(.*?)</a>", desc_html, re.IGNORECASE | re.DOTALL
    #             )
    #             for val_match in value_matches:
    #                 clean_val = clean_html_text(val_match)
    #                 # Filter out UI control symbols ("...", "…") and duplicates
    #                 if (
    #                     clean_val
    #                     and clean_val not in ["...", "…"]
    #                     and clean_val not in dom_values
    #                 ):
    #                     dom_values.append(clean_val)
    #         break

    #     if dom_values:
    #         game_data[field_name] = dom_values
    #         continue

    #     # JSON Fallback (Targets "name": "Value" key-value pairs)
    #     found_vals = []
    #     for key in json_keys:
    #         json_match = re.search(
    #             rf'"{key}"\s*:\s*(\[[^\]]*\]|\{{[^\}}]*\}})',
    #             html_content,
    #             re.IGNORECASE | re.DOTALL,
    #         )
    #         if json_match:
    #             raw_json_val = json_match.group(1)

    #             # Target ONLY the values associated with the "name" key in BGG's JSON payload
    #             extracted_names = re.findall(
    #                 r'"name"\s*:\s*"([^"]+)"', raw_json_val, re.IGNORECASE
    #             )

    #             for name in extracted_names:
    #                 clean_name = decode_json_string(name)
    #                 if clean_name and clean_name not in found_vals:
    #                     found_vals.append(clean_name)

    #             if found_vals:
    #                 break

    #     game_data[field_name] = found_vals

    # --- relationship fields ---
    game_data.update(parse_relationship_fields(html_content=html_content)) 
    # relationship_targets = [
    #     ("reimplements", "Reimplements", ["reimplements", "boardgamereimplements"]),
    #     (
    #         "reimplemented_by",
    #         "Reimplemented By",
    #         ["reimplementedby", "boardgamereimplementedby", "reimplementation"],
    #     ),
    #     (
    #         "integrates_with",
    #         "Integrates With",
    #         ["integrateswith", "boardgameintegration", "integrates"],
    #     ),
    #     ("contains", "Contains", ["contains", "boardgamecompilation", "compilation"]),
    #     ("contained_in", "Contained In", ["containedin", "contained_in"]),
    # ]

    # for field_name, dom_title, json_keys in relationship_targets:
    #     dom_values = []

    #     # Matches 'feature' or 'outline-item' wrappers
    #     item_pattern = r'<(?:li|div)\b[^>]*class=["\'][^"\']*\b(?:outline-item|feature)\b[^"\']*["\'][^>]*>(.*?)<\/(?:li|div)>'

    #     for item_match in re.finditer(
    #         item_pattern, html_content, re.IGNORECASE | re.DOTALL
    #     ):
    #         item_html = item_match.group(1)

    #         # Match title header (.feature-title or .outline-item-title)
    #         title_match = re.search(
    #             r'<(?:div|h4)\b[^>]*class=["\'][^"\']*\b(?:outline-item-title|feature-title)\b[^"\']*["\'][^>]*>(.*?)<\/(?:div|h4)>',
    #             item_html,
    #             re.IGNORECASE | re.DOTALL,
    #         )
    #         if not title_match:
    #             continue

    #         title_text = clean_html_text(title_match.group(1)).casefold()
    #         if dom_title.casefold() not in title_text:
    #             continue

    #         # Match description container (.feature-description or .outline-item-description)
    #         desc_pattern = r'<(?:div|span)\b[^>]*class=["\'][^"\']*\b(?:outline-item-description|feature-description)\b[^"\']*["\'][^>]*>(.*?)<\/(?:div|span)>'
    #         description_match = re.search(
    #             desc_pattern, item_html, re.IGNORECASE | re.DOTALL
    #         )

    #         if description_match:
    #             desc_html = description_match.group(1)

    #             # Extract anchor tags containing related game titles
    #             value_matches = re.findall(
    #                 r"<a\b[^>]*>(.*?)</a>", desc_html, re.IGNORECASE | re.DOTALL
    #             )
    #             for val_match in value_matches:
    #                 clean_val = clean_html_text(val_match)
    #                 # Filter out UI controls like "..." / "…" and prevent duplicates
    #                 if (
    #                     clean_val
    #                     and clean_val not in ["...", "…"]
    #                     and clean_val not in dom_values
    #                 ):
    #                     dom_values.append(clean_val)
    #         break

    #     if dom_values:
    #         game_data[field_name] = dom_values
    #         continue

    #     # Corrected JSON Fallback for Relational Fields
    #     found_vals = []
    #     for key in json_keys:
    #         json_match = re.search(
    #             rf'"{key}"\s*:\s*(\[[^\]]*\]|\{{[^\}}]*\}})',
    #             html_content,
    #             re.IGNORECASE | re.DOTALL,
    #         )
    #         if json_match:
    #             raw_json_val = json_match.group(1)

    #             # Extract values under "name" or "text" keys inside the embedded JSON object
    #             extracted_names = re.findall(
    #                 r'"(?:name|text)"\s*:\s*"([^"]+)"', raw_json_val, re.IGNORECASE
    #             )

    #             for name in extracted_names:
    #                 clean_name = decode_json_string(name)
    #                 if clean_name and clean_name not in found_vals:
    #                     found_vals.append(clean_name)

    #             if found_vals:
    #                 break

    #     game_data[field_name] = found_vals

    return game_data


# field_formats = {
#     "num_of_ratings": int,
#     "num_of_comments": int,
#     "playing_time_min": int,
#     "playing_time_max": int,
# }

# field_transforms = {
#     "overall_rank": lambda x: int(x) if x and int(x) > 0 else None,
#     "strategy_rank": lambda x: int(x) if x and int(x) > 0 else None,
#     "party_rank": lambda x: int(x) if x and int(x) > 0 else None,
#     "family_rank": lambda x: int(x) if x and int(x) > 0 else None,
#     "playing_time_min": lambda x: int(x) if x and int(x) > 0 else None,
#     "playing_time_max": lambda x: int(x) if x and int(x) > 0 else None,
# }

fields_to_reparse = ["num_of_ratings",  "play_time_min", "play_time_max"]

def process_games(
    input_file: Path,
    smart_append: bool = False,
    reparse_fields: bool = False,
    # backfill_missing: bool = False,
    # enforce_types: bool = False,
    # reparse_field=None,
):
    # Kompletná schéma datasetu zadefinovaná podľa zadania
    headers = [
        "app_id",
        "game_title",
        "release_year",
        "short_description",
        "num_of_ratings",
        # "num_of_comments",
        # "num_of_players",
        "num_of_players_min",
        "num_of_players_max",
        "play_time_min",
        "play_time_max",
        "age",
        "weight",
        "alternate_names",
        "designer",
        "artist",
        "publisher",
        "description",
        "awards_honors",
        "own",
        "prev_owned",
        "wishlist",
        "for_trade",
        "want_in_trade",
        "has_parts",
        "wants_parts",
        "avg_rating",
        "comments",
        "fans",
        "page_views",
        "overall_rank",
        "strategy_rank",
        "party_rank",
        "family_rank",
        "all_time_plays",
        "all_time_plays_this_month",
        "html_file_path",
        # --- classification fields ---
        "game_type",
        "game_category",
        "game_mechanic",
        "game_family",
        # --- relationship fields ---
        "reimplements",
        "reimplemented_by",
        "integrates_with",
        "contains",
        "contained_in",
    ]

    harvest_versioner = SmartVersioner(
        base_filename=input_file.stem, data_dir=input_file.parent
    )
    scraper_versioner = SmartVersioner(
        base_filename=OUTPUT_TSV.stem,
        data_dir=OUTPUT_TSV.parent,
        extension=OUTPUT_TSV.suffix,
    )

    # Načítanie zoznamu app_id z input TSV
    app_ids = []
    with harvest_versioner.open_latest_save_file() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            app_ids.append(row["app_id"])

    # now we run transformations on the existing scraped data if reparse_fields is True
    if reparse_fields:
        with scraper_versioner.open_latest_save_file() as f:
            reader = csv.DictReader(f, delimiter="\t")
            existing_data = list(reader)

        for row in existing_data:
            for field in fields_to_reparse:
                if field in row and row[field]:
                    try:
                        row[field] = int(row[field])
                    except ValueError:
                        row[field] = None

        # Save the transformed data back to the TSV file
        with scraper_versioner.open_latest_save_file("w") as f:
            writer = csv.DictWriter(f, fieldnames=headers, delimiter="\t")
            writer.writeheader()
            writer.writerows(existing_data)

    # Načítanie zoznamu už stiahnutých app_id z output TSV
    scraped_ids = set()

    
    with scraper_versioner.open_latest_save_file() as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            scraped_ids.add(row["app_id"])




    pending_app_ids = [
        app_id for app_id in app_ids if app_id not in scraped_ids
    ]
    already_scraped_count = len(app_ids) - len(pending_app_ids)

    tqdm.write(
        f"--- STARTING BGG SCRAPE & PARSE FOR {len(pending_app_ids)} GAMES "
        f"({already_scraped_count} already scraped) ---"
    )

    # Inštancia Playwright mimo slučky, aby sme nadväzovali spojenie iba raz
    with sync_playwright() as p:
        browser = None
        browser_page = None

        for idx, app_id in tqdm(
            enumerate(pending_app_ids, 1),
            total=len(pending_app_ids),
            desc="Processing Games",
            unit="game",
        ):
            file_path = os.path.join(OUTPUT_DIR, f"{app_id}.html")
            html_content = ""

            # Skontroluj, či už je HTML lokálne uložené
            if os.path.exists(file_path):
                tqdm.write(
                    f"[{idx}/{len(pending_app_ids)}] Loading cached HTML for app_id {app_id}..."
                )
                with open(file_path, "r", encoding="utf-8") as f:
                    html_content = f.read()
            else:
                # Ak HTML nemáme a Playwright ešte nebeží, pripoj sa (Lazy načítanie)
                if browser is None:
                    try:
                        browser = p.chromium.connect_over_cdp(CDP_URL)
                        context = browser.contexts[0]
                        browser_page = (
                            context.pages[0]
                            if context.pages
                            else context.new_page()
                        )
                    except Exception as e:
                        tqdm.write(
                            f"[ERROR] Could not connect to Chrome on {CDP_URL}! Details: {e}"
                        )
                        return

                tqdm.write(
                    f"[{idx}/{len(pending_app_ids)}] Fetching HTML for app_id {app_id} via CDP..."
                )
                url = f"https://boardgamegeek.com/boardgame/{app_id}/"

                try:
                    # Prejdeme na stránku a počkáme na stiahnutie Javascriptových dát
                    # browser_page.goto(url, wait_until="networkidle", timeout=30000)
                    # time.sleep(2)  # Krátky delay pre vyrenderovanie komponentov
                    # OPRAVENÝ KÓD
                    # domcontentloaded načíta štruktúru bez čakania na reklamy a trackery
                    browser_page.goto(
                        url, wait_until="domcontentloaded", timeout=30000
                    )

                    # Ak chceš mať istotu, že sa načítali dáta hry, počkáme, kým sa zjaví hlavný nadpis
                    try:
                        # Čakáme max 5 sekúnd na vyrenderovanie elementu, ktorý obsahuje rok alebo názov
                        browser_page.wait_for_selector(
                            "span.game-year", timeout=5000
                        )
                    except Exception:
                        # Ak sa nenájde nadpis (napr. hra nemá zadaný rok), počkáme natvrdo
                        time.sleep(3)

                    time.sleep(
                        1
                    )  # Dodatočná sekunda pre istotu, kým sa dočítajú hodnotenia

                    # Ochrana proti Cloudflare (rovnaká ako pri zbere ID)
                    if "Just a moment..." in browser_page.title():
                        tqdm.write(
                            f" -> Cloudflare triggered on {url}! Please solve manually in Chrome..."
                        )
                        while "Just a moment..." in browser_page.title():
                            time.sleep(2)
                        tqdm.write(" -> Challenge solved! Resuming...")

                    html_content = browser_page.content()

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(html_content)

                    # Náhodný sleep medzi požiadavkami, keď reálne sťahujeme
                    time.sleep(1.5)

                except Exception as e:
                    tqdm.write(f"  -> Error fetching page: {e}")
                    continue

            # Extrakcia a uloženie
            if html_content:
                game_data = parse_game_html(app_id, html_content)
                game_data["html_file_path"] = file_path
                writer.writerow(game_data)
                tqdm.write(
                f"  -> Parsed: {game_data.get('game_title', 'Unknown')} | Year: {game_data.get('release_year', 'N/A')} | Rating: {game_data.get('avg_rating', 'N/A')}"
                )

    scraper_versioner.dump_temp_to_final()


if __name__ == "__main__":
    process_games(
        args.input,
        smart_append=args.smart_append,
        reparse_fields=args.reparse_fields,
        # backfill_missing=args.backfill_missing,
        # enforce_types=args.enforce_types,
        # reparse_field=args.reparse_field,
    )
