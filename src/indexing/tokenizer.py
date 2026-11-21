
"""Shared text tokenization for BGG indexing and querying."""

import re


TOKENIZER_PATTERN = r"\b[a-zA-Z]{3,}\b"
TOKENIZER = re.compile(TOKENIZER_PATTERN)


def tokenize_text(text: str) -> list[str]:
    """Convert text into lowercase ASCII alphabetic tokens."""

    return TOKENIZER.findall(text.lower())
