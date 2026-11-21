
"""Query processing for the BGG search engine."""

from collections import Counter

from src.indexing.tokenizer import tokenize_text


def process_query(query: str) -> dict[str, int]:
    """Tokenize a search query and count its term frequencies."""

    tokens = tokenize_text(query)

    return dict(Counter(tokens))
