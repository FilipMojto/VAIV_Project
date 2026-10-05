

from pathlib import Path
import re

from src.config import DATA_DIR, HTML_DIR

def clean_html_text(text: str) -> str:
    """Removes HTML tags and normalizes whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()

def parse_play_fields(html_content: str) -> dict:
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
        if dom_value and (
            field_name != "all_time_plays" or int(dom_value) > 0
        ):
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


# I need a quick test to load existing tsv file and check if the parsing works correctly. I will create a test function that reads a sample TSV file, extracts the HTML content, and then calls the `parse_play_fields` function to verify the output.

if __name__ == "__main__":
    # Sample test for parse_play_fields function
    app_id = "test_436560"  # Replace with a valid app_id for testing
    # now load .html file using the app_id
    sample_html_path = Path(HTML_DIR) / f"{app_id}.html"
    if sample_html_path.exists():
        with open(sample_html_path, "r", encoding="utf-8") as file:
            html_content = file.read()
        result = parse_play_fields(html_content)
        print(result)  # Expected output: {'all_time_plays': '70925', 'all_time_plays_this_month': '1234'}
    else:
        raise FileNotFoundError(f"Sample HTML file not found: {sample_html_path}")

    # result = parse_play_fields(HTML_DIR / f"{app_id}.html")
    # print(result)  # Expected output: {'all_time_plays': '70925', 'all_time_plays_this_month': '1234'}
