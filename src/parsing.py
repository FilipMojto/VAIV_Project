from enum import StrEnum
import json
from pathlib import Path
import re
from typing import Callable, Dict

from src.config import HTML_DIR
from src.utils import load_html_file


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------


def clean_html_text(text: str) -> str:
    """Removes HTML tags and normalizes whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_count(text: str) -> str:
    """Return a count as digits only, preserving missing/invalid values as blank."""
    digits = re.sub(r"\D", "", text or "")
    return str(int(digits)) if digits else ""

def decode_json_string(value: str) -> str:
    """Decode a JSON string fragment, preserving it if the fragment is malformed."""
    try:
        return json.loads(f'"{value}"').strip()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return value.strip()


# -----------------------------------------------------------------------------
# Parsing Functions
# -----------------------------------------------------------------------------


def parse_general_fields(html_content: str) -> dict:
    """Extracts the game title, release year and alternate names
      from the HTML content."""

    game_data = {}
    # ZÁKLADNÉ METADÁTA (Príklady Regexov pre BGG)
    # Názov a rok sa často nachádzajú v title alebo v hlavičke
    title_match = re.search(
        r'<meta property="og:title" content="(.*?)(?:\s\(\d{4}\))?"', html_content
    )
    game_data["game_title"] = (
        clean_html_text(title_match.group(1)) if title_match else ""
    )

    year_match = re.search(
        r'<span[^>]*class="game-year"[^>]*>\s*\(\s*(\d+)\s*\)\s*</span>', html_content
    )
    game_data["release_year"] = year_match.group(1) if year_match else ""
    
    # --- alternate_names ---
    
    alt_names_matches = re.findall(
        r'<div[^>]*ng-switch-when="alternatename"[^>]*>\s*(.*?)\s*</div>',
        html_content,
        re.DOTALL,
    )

    if alt_names_matches:
        # Clean text and filter out empty strings
        cleaned_names = [
            clean_html_text(name) for name in alt_names_matches if clean_html_text(name)
        ]

        # Remove duplicates while preserving original order
        unique_names = list(dict.fromkeys(cleaned_names))

        # Join with pipe separator so commas inside titles won't disrupt parsing
        game_data["alternate_names"] = " | ".join(unique_names)
    else:
        # Fallback regex for embedded JSON data in the HTML source
        json_alt_matches = re.findall(
            r'"alternatenames"\s*:\s*\[(.*?)\]', html_content, re.DOTALL
        )
        if json_alt_matches:
            names_in_json = re.findall(r'"name"\s*:\s*"([^"]+)"', json_alt_matches[0])
            game_data["alternate_names"] = " | ".join(dict.fromkeys(names_in_json))
        else:
            game_data["alternate_names"] = ""
                
    return game_data

def parse_descriptions(html_content: str) -> dict:
    """Extracts short and long descriptions from the HTML content."""

    game_data = {}

    # --- short_description ---
    
    desc_match = re.search(r'<meta name="description" content="(.*?)"', html_content)
    game_data["short_description"] = (
        clean_html_text(desc_match.group(1)) if desc_match else ""
    )

    # --- description ---
    
    desc_match = re.search(
        r'<article class="game-description-body"[^>]*>(.*?)</article>',
        html_content,
        re.DOTALL,
    )

    if desc_match:
        raw_desc = desc_match.group(1)

        # Strip all inner HTML tags (e.g., <p>, <em>, <br>) and replace with spaces
        no_tags_desc = re.sub(r"<[^>]+>", " ", raw_desc)

        # Normalize spaces and strip newlines to ensure single-line TSV compatibility
        game_data["description"] = clean_html_text(no_tags_desc)
    else:
        # Fallback to BGG's embedded JSON object
        json_desc = re.search(
            r'"description"\s*:\s*"(.*?)(?<!\\)"', html_content, re.DOTALL
        )
        if json_desc:
            raw_json_desc = json_desc.group(1)
            # Decode JSON unicode escapes (e.g., \u0027 for apostrophes) and newlines (\n)
            decoded_desc = bytes(raw_json_desc, "utf-8").decode("unicode_escape")
            no_tags_json = re.sub(r"<[^>]+>", " ", decoded_desc)
            game_data["description"] = clean_html_text(no_tags_json)
        else:
            game_data["description"] = ""

    return game_data


def parse_game_metrics(html_content: str) -> dict:
    """Extracts various game metrics like number of players, play time, age, and weight from the HTML content."""

    game_data = {}
    min_match = re.search(
        r'<meta[^>]*itemprop="minValue"[^>]*content="(\d+)"', html_content
    )
    max_match = re.search(
        r'<meta[^>]*itemprop="maxValue"[^>]*content="(\d+)"', html_content
    )

    min_players = min_match.group(1) if min_match else ""
    max_players = max_match.group(1) if max_match else ""

    # Formátovanie výstupu (napr. "1–4" alebo "1" ak sa min a max rovnajú)
    game_data['num_of_players_min'] = min_players if min_players else ""
    game_data['num_of_players_max'] = max_players if max_players else ""

    min_time_match = re.search(
        r'<meta[^>]*itemprop="minplaytime"[^>]*content="(\d+)"',
        html_content,
        re.IGNORECASE,
    )
    max_time_match = re.search(
        r'<meta[^>]*itemprop="maxplaytime"[^>]*content="(\d+)"',
        html_content,
        re.IGNORECASE,
    )

    # Fallback regex in case meta tags are structured inside Angular JSON
    if not min_time_match:
        min_time_match = re.search(r'"minplaytime"\s*:\s*"?(\d+)"?', html_content)
    if not max_time_match:
        max_time_match = re.search(r'"maxplaytime"\s*:\s*"?(\d+)"?', html_content)

    min_time = min_time_match.group(1) if min_time_match else ""
    max_time = max_time_match.group(1) if max_time_match else ""

    if ( min_time == 0 or min_time == "0" ) or (max_time == 0 or max_time == "0"):
        print("HERE")

    game_data["play_time_min"] = "" if min_time == 0 or min_time == "0" else min_time 
    game_data["play_time_max"] = "" if max_time == 0 or max_time == "0" else max_time
 
    # Extract minimum age
    age_match = re.search(
        r'<span[^>]*itemprop="suggestedMinAge"[^>]*>\s*(\d+)\s*</span>', html_content
    )

    # Fallback in case raw JSON data is matched
    if not age_match:
        age_match = re.search(r'"minage"\s*:\s*"?(\d+)"?', html_content)

    game_data["age"] = f"{age_match.group(1)}+" if age_match else ""

    # Extrakcia náročnosti / váhy hry (weight)
    weight_match = re.search(
        r'<span[^>]*item-poll-button="boardgameweight"[^>]*>(.*?)</span>',
        html_content,
        re.DOTALL,
    )

    if weight_match:
        raw_weight = clean_html_text(weight_match.group(1))
        # Zachytí desatinné číslo (napr. "2.34" z textu "2.34 / 5")
        num_match = re.search(r"(\d+(?:\.\d+)?)", raw_weight)
        game_data["weight"] = num_match.group(1) if num_match else ""
    else:
        # Záložný regex pre raw HTML (údaje v vstavanom JSON objekte BGG)
        json_weight = re.search(
            r'"averageweight"\s*:\s*"?(\d+(?:\.\d+)?)"?', html_content
        )
        game_data["weight"] = json_weight.group(1) if json_weight else ""

    return game_data


def parse_game_classification(html_content: str) -> dict:
    """Extracts game classifications like type, category, mechanic, and family from the HTML content."""

    game_data = {}
    classification_targets = [
        (
            "game_type",
            "Type",
            ["boardgamesubdomain", "subdomain", "type", "boardgametype"],
        ),
        (
            "game_category",
            "Category",
            ["boardgamecategory", "category", "boardgamecategories"],
        ),
        (
            "game_mechanic",
            "Mechanism",
            ["boardgamemechanic", "mechanic", "boardgamemechanics", "mechanics"],
        ),
        ("game_family", "Family", ["boardgamefamily", "family", "boardgamefamilies"]),
    ]

    for field_name, dom_title, json_keys in classification_targets:
        dom_values = []

        # BGG classification fields use 'feature' blocks or 'outline-item' wrappers
        item_pattern = r'<(?:li|div)\b[^>]*class=["\'][^"\']*\b(?:outline-item|feature)\b[^"\']*["\'][^>]*>(.*?)<\/(?:li|div)>'

        for item_match in re.finditer(
            item_pattern, html_content, re.IGNORECASE | re.DOTALL
        ):
            item_html = item_match.group(1)

            # Match the title container (.outline-item-title or .feature-title)
            title_match = re.search(
                r'<(?:div|h4)\b[^>]*class=["\'][^"\']*\b(?:outline-item-title|feature-title)\b[^"\']*["\'][^>]*>(.*?)<\/(?:div|h4)>',
                item_html,
                re.IGNORECASE | re.DOTALL,
            )
            if not title_match:
                continue

            title_text = clean_html_text(title_match.group(1)).casefold()
            if dom_title.casefold() not in title_text:
                continue

            # Match the description container (.outline-item-description or .feature-description)
            desc_pattern = r'<(?:div|span)\b[^>]*class=["\'][^"\']*\b(?:outline-item-description|feature-description)\b[^"\']*["\'][^>]*>(.*?)<\/(?:div|span)>'
            description_match = re.search(
                desc_pattern, item_html, re.IGNORECASE | re.DOTALL
            )

            if description_match:
                desc_html = description_match.group(1)

                # Extract all anchor tags containing classification labels (e.g., "Creatures: Monsters", "Crowdfunding: Kickstarter")
                value_matches = re.findall(
                    r"<a\b[^>]*>(.*?)</a>", desc_html, re.IGNORECASE | re.DOTALL
                )
                for val_match in value_matches:
                    clean_val = clean_html_text(val_match)
                    # Filter out UI control symbols ("...", "…") and duplicates
                    if (
                        clean_val
                        and clean_val not in ["...", "…"]
                        and clean_val not in dom_values
                    ):
                        dom_values.append(clean_val)
            break

        if dom_values:
            game_data[field_name] = dom_values
            continue

        # JSON Fallback (Targets "name": "Value" key-value pairs)
        found_vals = []
        for key in json_keys:
            json_match = re.search(
                rf'"{key}"\s*:\s*(\[[^\]]*\]|\{{[^\}}]*\}})',
                html_content,
                re.IGNORECASE | re.DOTALL,
            )
            if json_match:
                raw_json_val = json_match.group(1)

                # Target ONLY the values associated with the "name" key in BGG's JSON payload
                extracted_names = re.findall(
                    r'"name"\s*:\s*"([^"]+)"', raw_json_val, re.IGNORECASE
                )

                for name in extracted_names:
                    clean_name = decode_json_string(name)
                    if clean_name and clean_name not in found_vals:
                        found_vals.append(clean_name)

                if found_vals:
                    break

        game_data[field_name] = found_vals

    return game_data


def parse_game_credits(html_content: str) -> dict:
    """Extracts game credits like designer, artist, and publisher from the HTML content."""

    game_data = {}
    # --- designer ---
    # Extract all designers
    designer_matches = re.findall(
        r'<a[^>]*href="[^"]*/boardgamedesigner/\d+/[^"]*"[^>]*>\s*(.*?)\s*</a>',
        html_content,
        re.DOTALL,
    )

    if designer_matches:
        # Clean HTML text for each designer name
        cleaned_designers = [
            clean_html_text(d) for d in designer_matches if clean_html_text(d)
        ]

        # Deduplicate while preserving order
        unique_designers = list(dict.fromkeys(cleaned_designers))

        # Join multiple designers with a comma (e.g., "Bruno Cathala, Antoine Bauza")
        game_data["designer"] = ", ".join(unique_designers)
    else:
        # Fallback for embedded JSON data in raw HTML
        json_designers = re.findall(
            r'"boardgamedesigner"\s*:\s*\[(.*?)\]', html_content, re.DOTALL
        )
        if json_designers:
            names = re.findall(r'"name"\s*:\s*"([^"]+)"', json_designers[0])
            game_data["designer"] = ", ".join(dict.fromkeys(names))
        else:
            game_data["designer"] = ""
    
    # --- artist ---
    # Extract all artists
    artist_matches = re.findall(
        r'<a[^>]*href="[^"]*/boardgameartist/\d+/[^"]*"[^>]*>\s*(.*?)\s*</a>',
        html_content,
        re.DOTALL,
    )

    if artist_matches:
        # Clean HTML text for each artist name
        cleaned_artists = [
            clean_html_text(a) for a in artist_matches if clean_html_text(a)
        ]

        # Deduplicate while preserving order
        unique_artists = list(dict.fromkeys(cleaned_artists))

        # Join multiple artists with a comma
        game_data["artist"] = ", ".join(unique_artists)
    else:
        # Fallback for embedded JSON data in raw HTML
        json_artists = re.findall(
            r'"boardgameartist"\s*:\s*\[(.*?)\]', html_content, re.DOTALL
        )
        if json_artists:
            names = re.findall(r'"name"\s*:\s*"([^"]+)"', json_artists[0])
            game_data["artist"] = ", ".join(dict.fromkeys(names))
        else:
            game_data["artist"] = ""

    # --- publisher ---
    # Extract all publishers by strictly matching text inside the anchor tags
    # Skip the DOM entirely to bypass lazy-loading truncation
    # Target the complete list stored in BGG's embedded JSON object
    json_block = re.search(
        r'"boardgamepublisher"\s*:\s*\[(.*?)\]', html_content, re.DOTALL
    )

    publishers = []
    if json_block:
        # Extract all "name" values from the matched JSON array
        json_names = re.findall(r'"name"\s*:\s*"([^"]+)"', json_block.group(1))

        for name in json_names:
            # Decode unicode characters (e.g., converting "Lookout\u0020Games" to "Lookout Games")
            decoded_name = bytes(name, "utf-8").decode("unicode_escape")
            if decoded_name not in publishers:
                publishers.append(decoded_name)

    # Join unique publishers with a pipe separator
    game_data["publisher"] = " | ".join(publishers)

    return game_data


def parse_game_ranks(html_content: str) -> dict:
    """Extracts game ranks like overall_rank, strategy_rank, party_rank, and family_rank from the HTML content."""

    game_data = {}
    rank_targets = [
        ("overall_rank", "Overall Rank", ["Board Game Rank", "Overall Rank"]),
        ("strategy_rank", "Strategy Rank", ["Strategy Rank", "Strategy Game Rank"]),
        ("party_rank", "Party Rank", ["Party Game Rank", "Party Rank"]),
        ("family_rank", "Family Rank", ["Family Game Rank", "Family Rank"]),
    ]   

    # BGG embeds ranks in rankinfo objects, e.g.:
    # {"shortprettyname":"Strategy Rank", "rank":"55", ...}
    rankinfo_match = re.search(
        r'"rankinfo"\s*:\s*\[(.*?)\]', html_content, re.IGNORECASE | re.DOTALL
    )
    rankinfo_entries = []
    if rankinfo_match:
        rankinfo_entries = re.findall(r"\{(.*?)\}", rankinfo_match.group(1), re.DOTALL)

    for field_name, dom_title, json_keys in rank_targets:
        dom_value = ""
        item_pattern = (
            r'<li\b[^>]*class=["\'][^"\']*\boutline-item\b[^"\']*["\'][^>]*>(.*?)</li>'
        )

        for item_match in re.finditer(
            item_pattern, html_content, re.IGNORECASE | re.DOTALL
        ):
            item_html = item_match.group(1)

            # Match the title container
            title_match = re.search(
                r'<div\b[^>]*class=["\'][^"\']*\boutline-item-title\b[^"\']*["\'][^>]*>(.*?)</div>',
                item_html,
                re.IGNORECASE | re.DOTALL,
            )
            if not title_match:
                continue

            title_text = clean_html_text(title_match.group(1)).casefold()
            if not title_text.startswith(dom_title.casefold()):
                continue

            # Match the description container
            description_match = re.search(
                r'<div\b[^>]*class=["\'][^"\']*\boutline-item-description\b[^"\']*["\'][^>]*>(.*?)</div>',
                item_html,
                re.IGNORECASE | re.DOTALL,
            )
            if description_match:
                desc_html = description_match.group(1)

                # Extract from the rank anchor tag (which carries class="rank-value")
                value_match = re.search(
                    r"<a\b[^>]*>(.*?)</a>", desc_html, re.IGNORECASE | re.DOTALL
                )
                if value_match:
                    dom_value = re.sub(
                        r"[^\d]", "", clean_html_text(value_match.group(1))
                    )
            break

        if dom_value:
            game_data[field_name] = dom_value
            continue

        # Match the rankinfo entry by its display name, not by a synthetic
        # key such as "strategyrank" (which BGG does not provide).
        found_val = ""
        for entry in rankinfo_entries:
            name_match = re.search(
                r'"(?:shortprettyname|prettyname)"\s*:\s*"((?:\\.|[^"\\])*)"',
                entry,
                re.IGNORECASE,
            )
            value_match = re.search(r'"rank"\s*:\s*"?(\d+)"?', entry, re.IGNORECASE)
            if (
                name_match
                and value_match
                and name_match.group(1).casefold() in [n.casefold() for n in json_keys]
            ):
                found_val = value_match.group(1)
                break

        # Retain compatibility with older cached pages that expose direct keys.
        if not found_val:
            legacy_keys = {
                "overall_rank": ["overallrank", "rank"],
                "strategy_rank": ["strategyrank"],
                "party_rank": ["partyrank"],
                "family_rank": ["familyrank"],
            }[field_name]
            for key in legacy_keys:
                json_match = re.search(
                    rf'"{key}"\s*:\s*"?(\d+)"?', html_content, re.IGNORECASE
                )
                if json_match:
                    found_val = json_match.group(1)
                    break
        game_data[field_name] = found_val

    ranks_to_update = []
    for rank, value in game_data.items():
        if value == 0 or value == "0":
            ranks_to_update.append(rank)

    for rank in ranks_to_update:
        game_data[rank] = ""

    return game_data


def parse_general_stats(html_content: str) -> dict:
    """Extracts general statistics like number of ratings, comments, fans, and page views from the HTML content."""
    
    game_data = {}

    # Extract Number of Ratings
    ratings_match = re.search(
        r'<a[^>]*href="[^"]*/ratings\?rated=1"[^>]*>\s*(.*?)\s*</a>', html_content
    )
    game_data["num_of_ratings"] = (
        parse_count(clean_html_text(ratings_match.group(1))) if ratings_match else ""
    )

    stat_targets = [
            ("comments", "Comments", ["numcomments", "comments"]),
            ("fans", "Fans", ["numfans", "fans"]),
            (
                "page_views",
                "Page Views",
                ["numpageviews", "pageviews", "views", "numviews"],
            ),
        ]
    
    for field_name, dom_title, json_keys in stat_targets:
        dom_value = ""
        item_pattern = (
            r'<li\b[^>]*class=["\'][^"\']*\boutline-item\b[^"\']*["\'][^>]*>(.*?)</li>'
        )

        for item_match in re.finditer(
            item_pattern, html_content, re.IGNORECASE | re.DOTALL
        ):
            item_html = item_match.group(1)

            # Match the title container
            title_match = re.search(
                r'<div\b[^>]*class=["\'][^"\']*\boutline-item-title\b[^"\']*["\'][^>]*>(.*?)</div>',
                item_html,
                re.IGNORECASE | re.DOTALL,
            )
            if not title_match:
                continue

            title_text = clean_html_text(title_match.group(1)).casefold()
            # Use exact or clean inclusion match since titles like "Comments" do not have a colon
            if dom_title.casefold() not in title_text:
                continue

            # Match the description container
            description_match = re.search(
                r'<div\b[^>]*class=["\'][^"\']*\boutline-item-description\b[^"\']*["\'][^>]*>(.*?)</div>',
                item_html,
                re.IGNORECASE | re.DOTALL,
            )
            if description_match:
                desc_html = description_match.group(1)

                # 1. Try extracting from an <a> tag first (Comments, Fans)
                value_match = re.search(
                    r"<a\b[^>]*>(.*?)</a>", desc_html, re.IGNORECASE | re.DOTALL
                )
                if value_match:
                    raw_val = value_match.group(1)
                else:
                    # 2. Fallback to raw text inside description if no <a> tag exists (Page Views)
                    raw_val = desc_html

                dom_value = re.sub(r"[^\d]", "", clean_html_text(raw_val))
            break

        if dom_value:
            game_data[field_name] = dom_value
            continue

        # JSON Fallback (Runs only if the DOM block is missing)
        found_val = ""
        for key in json_keys:
            json_match = re.search(
                rf'"{key}"\s*:\s*"?(\d+)"?', html_content, re.IGNORECASE
            )
            if json_match:
                found_val = json_match.group(1)
                break
        game_data[field_name] = found_val

    return game_data


def parse_player_stats(html_content: str) -> dict:
    """Extracts player statistics like own, prev_owned, for_trade, want_in_trade, wishlist, has_parts, and wants_parts from the HTML content."""

    game_data = {}
    # Map each field to its clean search token and expanded JSON keys
    # Map each field to its exact DOM title and potential JSON fallback keys
    # Unified stat extraction bypassing all HTML attributes
    stat_targets = [
        ("own", "Own", ["numowned", "owned"]),
        ("prev_owned", "Prev. Owned", ["numprevowned", "prevowned"]),
        ("for_trade", "For Trade", ["numfortrade", "fortrade"]),
        ("want_in_trade", "Want In Trade", ["numwanting", "wanting", "numwant"]),
        (
            "wishlist",
            "Wishlist",
            ["numwishing", "wishing", "wishlist", "numwishlist", "numwish"],
        ),
        ("has_parts", "Has Parts", ["numhasparts", "hasparts"]),
        (
            "wants_parts",
            "Want Parts",
            ["numwantparts", "wantparts", "numwantingparts", "wantingparts"],
        ),
    ]

    for field_name, dom_title, json_keys in stat_targets:
        # Each statistic is an outline-item with a title and a separate
        # description. Match within that item so title-side links (such as
        # "Find For Trade Matches") cannot be mistaken for the count.
        dom_value = ""
        item_pattern = (
            r'<li\b[^>]*class=["\'][^"\']*\boutline-item\b[^"\']*["\'][^>]*>(.*?)</li>'
        )
        for item_match in re.finditer(
            item_pattern, html_content, re.IGNORECASE | re.DOTALL
        ):
            item_html = item_match.group(1)
            title_match = re.search(
                r'<div\b[^>]*class=["\'][^"\']*\boutline-item-title\b[^"\']*["\'][^>]*>(.*?)</div>',
                item_html,
                re.IGNORECASE | re.DOTALL,
            )
            if not title_match:
                continue

            title_text = clean_html_text(title_match.group(1)).casefold()
            if not re.match(rf"^{re.escape(dom_title.casefold())}\s*:", title_text):
                continue

            description_match = re.search(
                r'<div\b[^>]*class=["\'][^"\']*\boutline-item-description\b[^"\']*["\'][^>]*>(.*?)</div>',
                item_html,
                re.IGNORECASE | re.DOTALL,
            )
            if description_match:
                value_match = re.search(
                    r"<a\b[^>]*>(.*?)</a>",
                    description_match.group(1),
                    re.IGNORECASE | re.DOTALL,
                )
                if value_match:
                    dom_value = re.sub(
                        r"[^\d]", "", clean_html_text(value_match.group(1))
                    )
            break

        # BGG displays "--" for unranked categories but embeds those as rank 0.
        # Keep unspecified ranks blank so they pass the non-negative rank check.
        if dom_value and int(dom_value) > 0:
            game_data[field_name] = dom_value
            continue

        # JSON Fallback (Runs only if the DOM block is entirely missing)
        found_val = ""
        for key in json_keys:
            json_match = re.search(
                rf'"{key}"\s*:\s*"?(\d+)"?', html_content, re.IGNORECASE
            )
            if json_match:
                found_val = json_match.group(1)
                break
        game_data[field_name] = found_val if found_val and int(found_val) > 0 else ""

    return game_data


def parse_player_plays_stats(html_content: str) -> dict:
    game_data = {}

    play_targets = [
        ("all_time_plays", "All Time Plays", ["numplays"]),
        (
            "all_time_plays_this_month",
            "This Month",
            ["numplaysthismonth", "numplays_month"],
        ),
    ]

    for field_name, dom_title, json_keys in play_targets:
        dom_value = ""
        item_pattern = (
            r'<li\b[^>]*class=["\'][^"\']*\boutline-item\b[^"\']*["\'][^>]*>(.*?)</li>'
        )

        for item_match in re.finditer(
            item_pattern, html_content, re.IGNORECASE | re.DOTALL
        ):
            item_html = item_match.group(1)

            # Match title header
            title_match = re.search(
                r'<div\b[^>]*class=["\'][^"\']*\boutline-item-title\b[^"\']*["\'][^>]*>(.*?)</div>',
                item_html,
                re.IGNORECASE | re.DOTALL,
            )
            if not title_match:
                continue

            title_text = clean_html_text(title_match.group(1)).casefold()
            if dom_title.casefold() not in title_text:
                continue

            # Match description container
            description_match = re.search(
                r'<div\b[^>]*class=["\'][^"\']*\boutline-item-description\b[^"\']*["\'][^>]*>(.*?)</div>',
                item_html,
                re.IGNORECASE | re.DOTALL,
            )
            if description_match:
                desc_html = description_match.group(1)

                # Extract anchor text and preserve digits only (handles commas like "70,925")
                value_match = re.search(
                    r"<a\b[^>]*>(.*?)</a>", desc_html, re.IGNORECASE | re.DOTALL
                )
                if value_match:
                    extracted_text = clean_html_text(value_match.group(1))
                    # Ensure we matched actual numbers and not unrendered Angular template syntax {{...}}
                    digits_only = re.sub(r"[^\d]", "", extracted_text)
                    if (
                        digits_only
                        and not extracted_text.startswith("{")
                        and (field_name != "all_time_plays" or int(digits_only) > 0)
                    ):
                        dom_value = digits_only
                        break

            # Some pages contain more than one matching row (including hidden
            # placeholders). Continue until this row actually yields a value.
            if dom_value:
                break

        # A visible zero for lifetime plays can be a placeholder/stale value
        # while the embedded item data contains the actual count. Try the
        # structured value before accepting that zero. Monthly zero is valid.
        if dom_value and (field_name != "all_time_plays" or int(dom_value) > 0):
            game_data[field_name] = dom_value
            continue

        # Strict JSON Fallback (Matches exact BGG stats keys)
        found_val = ""
        for key in json_keys:
            # Prefer a positive lifetime count if the page embeds an earlier
            # zero placeholder as well as the populated statistic.
            json_matches = re.finditer(
                rf'"{key}"\s*:\s*"?([\d,]+)"?', html_content, re.IGNORECASE
            )
            for json_match in json_matches:
                candidate = re.sub(r"[^\d]", "", json_match.group(1))
                if not candidate:
                    continue
                if field_name != "all_time_plays" or int(candidate) > 0:
                    found_val = candidate
                    break
                # Keep zero only if no positive lifetime count is present.
                found_val = candidate
            if found_val and (field_name != "all_time_plays" or int(found_val) > 0):
                break

        game_data[field_name] = found_val

    # Lifetime plays cannot be lower than the plays recorded this month. If
    # BGG supplied a zero lifetime placeholder and no usable JSON fallback,
    # leave it blank instead of exporting a contradictory zero.
    lifetime = game_data.get("all_time_plays", "")
    monthly = game_data.get("all_time_plays_this_month", "")
    if lifetime and monthly and int(lifetime) < int(monthly):
        game_data["all_time_plays"] = ""

    return game_data


def parse_ratings_and_awards(html_content: str) -> dict:
    """Extracts ratings and awards/honors from the HTML content."""

    game_data = {}

    # --- avg_rating ---
    

    rating_targets = [
        (
            "avg_rating",
            "Avg. Rating",
            ["averagerating", "avg_rating", "rating", "average"],
        )
    ]

    for field_name, dom_title, json_keys in rating_targets:
        dom_value = ""
        item_pattern = (
            r'<li\b[^>]*class=["\'][^"\']*\boutline-item\b[^"\']*["\'][^>]*>(.*?)</li>'
        )

        for item_match in re.finditer(
            item_pattern, html_content, re.IGNORECASE | re.DOTALL
        ):
            item_html = item_match.group(1)

            # Match the title container
            title_match = re.search(
                r'<div\b[^>]*class=["\'][^"\']*\boutline-item-title\b[^"\']*["\'][^>]*>(.*?)</div>',
                item_html,
                re.IGNORECASE | re.DOTALL,
            )
            if not title_match:
                continue

            title_text = clean_html_text(title_match.group(1)).casefold()
            if dom_title.casefold() not in title_text:
                continue

            # Match the description container
            description_match = re.search(
                r'<div\b[^>]*class=["\'][^"\']*\boutline-item-description\b[^"\']*["\'][^>]*>(.*?)</div>',
                item_html,
                re.IGNORECASE | re.DOTALL,
            )
            if description_match:
                desc_html = description_match.group(1)

                # Extract from the anchor tag
                value_match = re.search(
                    r"<a\b[^>]*>(.*?)</a>", desc_html, re.IGNORECASE | re.DOTALL
                )
                if value_match:
                    raw_val = clean_html_text(value_match.group(1))
                    # Keep digits AND the decimal point (e.g., "8.130" remains "8.130")
                    dom_value = re.sub(r"[^\d.]", "", raw_val)
            break

        if dom_value:
            game_data[field_name] = dom_value
            continue

        # JSON Fallback (Floating-point safe matching)
        found_val = ""
        for key in json_keys:
            json_match = re.search(
                rf'"{key}"\s*:\s*"?([\d.]+)"?', html_content, re.IGNORECASE
            )
            if json_match:
                found_val = json_match.group(1)
                break
        game_data[field_name] = found_val

    # --- awards_honors ---
    # Extract all awards and honors by strictly matching text inside the anchor tags
    award_matches = re.findall(
        r'<a[^>]*href="[^"]*/boardgamehonor/\d+/[^"]*"[^>]*>\s*([^<]+?)\s*</a>',
        html_content,
    )

    awards = []
    if award_matches:
        for a in award_matches:
            clean_name = clean_html_text(a)
            if clean_name and clean_name not in awards:
                awards.append(clean_name)

    # Fallback to BGG's embedded JSON object in case DOM rendering is incomplete
    if not awards or len(awards) <= 2:
        json_block = re.search(
            r'"boardgamehonor"\s*:\s*\[(.*?)\]', html_content, re.DOTALL
        )
        if json_block:
            # Match JSON strings including escaped quotes and backslashes. The
            # unicode_escape codec rejects valid names ending in a backslash
            # and can corrupt non-ASCII text; let the JSON decoder handle them.
            json_names = re.findall(
                r'"name"\s*:\s*("(?:\\.|[^"\\])*")', json_block.group(1)
            )
            for encoded_name in json_names:
                try:
                    decoded_name = json.loads(encoded_name)
                except json.JSONDecodeError:
                    # Preserve the extracted text if the embedded page data is
                    # malformed, rather than aborting the entire game scrape.
                    decoded_name = encoded_name[1:-1]
                decoded_name = clean_html_text(decoded_name)
                if decoded_name not in awards:
                    awards.append(decoded_name)

    # Join unique awards with a pipe separator (awards often contain commas)
    game_data["awards_honors"] = " | ".join(awards)

    return game_data


def parse_relationship_fields(html_content: str) -> dict:
    """Extracts fields representing relationships with other games."""

    game_data = {}
    relationship_targets = [
        ("reimplements", "Reimplements", ["reimplements", "boardgamereimplements"]),
        (
            "reimplemented_by",
            "Reimplemented By",
            ["reimplementedby", "boardgamereimplementedby", "reimplementation"],
        ),
        (
            "integrates_with",
            "Integrates With",
            ["integrateswith", "boardgameintegration", "integrates"],
        ),
        ("contains", "Contains", ["contains", "boardgamecompilation", "compilation"]),
        ("contained_in", "Contained In", ["containedin", "contained_in"]),
    ]

    for field_name, dom_title, json_keys in relationship_targets:
        dom_values = []

        # Matches 'feature' or 'outline-item' wrappers
        item_pattern = r'<(?:li|div)\b[^>]*class=["\'][^"\']*\b(?:outline-item|feature)\b[^"\']*["\'][^>]*>(.*?)<\/(?:li|div)>'

        for item_match in re.finditer(
            item_pattern, html_content, re.IGNORECASE | re.DOTALL
        ):
            item_html = item_match.group(1)

            # Match title header (.feature-title or .outline-item-title)
            title_match = re.search(
                r'<(?:div|h4)\b[^>]*class=["\'][^"\']*\b(?:outline-item-title|feature-title)\b[^"\']*["\'][^>]*>(.*?)<\/(?:div|h4)>',
                item_html,
                re.IGNORECASE | re.DOTALL,
            )
            if not title_match:
                continue

            title_text = clean_html_text(title_match.group(1)).casefold()
            if dom_title.casefold() not in title_text:
                continue

            # Match description container (.feature-description or .outline-item-description)
            desc_pattern = r'<(?:div|span)\b[^>]*class=["\'][^"\']*\b(?:outline-item-description|feature-description)\b[^"\']*["\'][^>]*>(.*?)<\/(?:div|span)>'
            description_match = re.search(
                desc_pattern, item_html, re.IGNORECASE | re.DOTALL
            )

            if description_match:
                desc_html = description_match.group(1)

                # Extract anchor tags containing related game titles
                value_matches = re.findall(
                    r"<a\b[^>]*>(.*?)</a>", desc_html, re.IGNORECASE | re.DOTALL
                )
                for val_match in value_matches:
                    clean_val = clean_html_text(val_match)
                    # Filter out UI controls like "..." / "…" and prevent duplicates
                    if (
                        clean_val
                        and clean_val not in ["...", "…"]
                        and clean_val not in dom_values
                    ):
                        dom_values.append(clean_val)
            break

        if dom_values:
            game_data[field_name] = dom_values
            continue

        # Corrected JSON Fallback for Relational Fields
        found_vals = []
        for key in json_keys:
            json_match = re.search(
                rf'"{key}"\s*:\s*(\[[^\]]*\]|\{{[^\}}]*\}})',
                html_content,
                re.IGNORECASE | re.DOTALL,
            )
            if json_match:
                raw_json_val = json_match.group(1)

                # Extract values under "name" or "text" keys inside the embedded JSON object
                extracted_names = re.findall(
                    r'"(?:name|text)"\s*:\s*"([^"]+)"', raw_json_val, re.IGNORECASE
                )

                for name in extracted_names:
                    clean_name = decode_json_string(name)
                    if clean_name and clean_name not in found_vals:
                        found_vals.append(clean_name)

                if found_vals:
                    break

        game_data[field_name] = found_vals
    
    return game_data


class ParserGroup(StrEnum):
    GENERAL_FIELDS = "general_fields"
    DESCRIPTIONS = "descriptions"
    GAME_METRICS = "game_metrics"
    GAME_CLASSIFICATION = "game_classification"
    GAME_CREDITS = "game_credits"
    RATING_AND_AWARDS = "rating_and_awards"
    GENERAL_STATS = "general_stats"
    PLAYER_STATS = "player_stats"
    PLAYER_PLAYS_STATS = "player_plays_stats"
    GAME_RANKS = "game_ranks"
    RELATIONSHIP_FIELDS = "relationship_fields"

GROUP_FIELD_MAPPINGS: Dict[ParserGroup, list[str]] = {
    ParserGroup.GENERAL_FIELDS: [
        "game_title",
        "release_year",
        "alternate_names",
    ],
    ParserGroup.DESCRIPTIONS: [
        "short_description",
        "description",
    ],
    ParserGroup.GAME_METRICS: [
        "num_of_players_min",
        "num_of_players_max",
        "play_time_min",
        "play_time_max",
        "age",
        "weight",
    ],
    ParserGroup.GAME_CLASSIFICATION: [
        "game_type",
        "game_category",
        "game_mechanic",
        "game_family",
    ],
    ParserGroup.GAME_CREDITS: [
        "designer",
        "artist",
        "publisher",
    ],
    ParserGroup.RATING_AND_AWARDS: [
        "avg_rating",
        "awards_honors",
    ],
    ParserGroup.GENERAL_STATS: [
        "num_of_ratings",
        "comments",
        "page_views",
        "fans",
    ],
    ParserGroup.PLAYER_STATS: [
        "own",
        "prev_owned",
        "for_trade",
        "want_in_trade",
        "wishlist",
        "has_parts",
        "wants_parts",
    ],
    ParserGroup.PLAYER_PLAYS_STATS: [
        "all_time_plays",
        "all_time_plays_this_month",
    ],
    ParserGroup.GAME_RANKS: [
        "overall_rank",
        "strategy_rank",
        "party_rank",
        "family_rank",
    ],
    ParserGroup.RELATIONSHIP_FIELDS: [
        "reimplements",
        "reimplemented_by",
        "integrates_with",
        "contains",
        "contained_in",
    ],
}

# 1. Mapping dictionary built with symbols (F2 safe)
parsing_mappings: Dict[ParserGroup, Callable] = {
    ParserGroup.GENERAL_FIELDS: parse_general_fields,
    ParserGroup.DESCRIPTIONS: parse_descriptions,
    ParserGroup.GAME_METRICS: parse_game_metrics,
    ParserGroup.GAME_CLASSIFICATION: parse_game_classification,
    ParserGroup.GAME_CREDITS: parse_game_credits,
    ParserGroup.RATING_AND_AWARDS: parse_ratings_and_awards,
    ParserGroup.GENERAL_STATS: parse_general_stats,
    ParserGroup.PLAYER_STATS: parse_player_stats,
    ParserGroup.PLAYER_PLAYS_STATS: parse_player_plays_stats,
    ParserGroup.GAME_RANKS: parse_game_ranks,
    ParserGroup.RELATIONSHIP_FIELDS: parse_relationship_fields,
}


if __name__ == "__main__":
    # Sample test for parse_play_fields function
    app_id = "test_436560"  # Replace with a valid app_id for testing
    # now load .html file using the app_id
    sample_html_path = Path(HTML_DIR) / f"{app_id}.html"
    loaded_html = load_html_file(app_id)