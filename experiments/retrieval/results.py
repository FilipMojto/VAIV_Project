
"""Standardised search result representation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    """A ranked search result."""

    app_id: str
    game_title: str
    score: float
    rank: int
