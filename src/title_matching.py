"""Unicode decoding and title normalization for BGG title matching."""

import re
from typing import Iterable
import unicodedata


_UNICODE_PAIR_PATTERN = re.compile(
    r"\\u([dD][89aAbB][0-9a-fA-F]{2})\\u([dD][c-fC-F][0-9a-fA-F]{2})"
)
_UNICODE_PATTERN = re.compile(r"\\u([0-9a-fA-F]{4})")


def decode_unicode_escapes(text: str) -> str:
    """Decode valid literal Unicode escapes without altering other characters."""

    def replace_pair(match: re.Match) -> str:
        high = int(match.group(1), 16)
        low = int(match.group(2), 16)
        codepoint = 0x10000 + ((high - 0xD800) << 10) + (low - 0xDC00)
        return chr(codepoint)

    def replace_character(match: re.Match) -> str:
        codepoint = int(match.group(1), 16)

        # Leave unpaired UTF-16 surrogates untouched.
        if 0xD800 <= codepoint <= 0xDFFF:
            return match.group(0)

        return chr(codepoint)

    text = _UNICODE_PAIR_PATTERN.sub(replace_pair, text)
    return _UNICODE_PATTERN.sub(replace_character, text)


def split_alternate_names(text: str | None) -> list[str]:
    """Split pipe-separated alternate names and decode each non-empty name."""

    if not text:
        return []

    return [
        name
        for part in text.split("|")
        if (name := decode_unicode_escapes(part.strip()))
    ]


def normalize_title(text: str) -> str:
    """Create a case-insensitive Unicode title key with normalized separators."""

    decoded = decode_unicode_escapes(text)
    normalized = unicodedata.normalize("NFKC", decoded).casefold()

    # Preserve letters, numbers, and combining marks.
    # Replace punctuation, symbols, and other characters with spaces.
    normalized = "".join(
        char if unicodedata.category(char)[0] in {"L", "N", "M"} else " "
        for char in normalized
    )

    return " ".join(normalized.split())


def get_title_variants(
    title: str,
    alternate_names: str | None = None,
) -> list[tuple[str, str, str]]:
    """Return unique (original spelling, normalized key, variant type) tuples."""

    candidates = [(decode_unicode_escapes(title), "primary")]

    candidates.extend(
        (name, "alternate")
        for name in split_alternate_names(alternate_names)
    )

    variants = []
    seen_keys = set()

    for candidate, variant_type in candidates:
        original = candidate.strip()
        key = normalize_title(original)

        if key and key not in seen_keys:
            variants.append((original, key, variant_type))
            seen_keys.add(key)

    return variants


def build_title_match_index(
    records: Iterable[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    """
    Build a normalized-title index mapping BGG title variants to game records.

    Each normalized title maps to a list of matching BGG games. Multiple
    games sharing the same normalized title are preserved.
    """
    title_index: dict[str, list[dict[str, str]]] = {}

    for record in records:
        app_id = record["app_id"].strip()
        game_title = decode_unicode_escapes(record["game_title"]).strip()

        if not app_id or not game_title:
            raise ValueError("BGG records must contain app_id and game_title.")

        variants = get_title_variants(
            game_title,
            record.get("alternate_names"),
        )

        for matched_variant, normalized_key, variant_type in variants:
            match = {
                "app_id": app_id,
                "game_title": game_title,
                "matched_variant": matched_variant,
                "variant_type": variant_type,
            }

            title_index.setdefault(normalized_key, []).append(match)

    return title_index
