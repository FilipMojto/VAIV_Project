
"""Retrieve candidate documents for processed search queries."""


from collections.abc import Iterator


def retrieve_candidates(
    index,
    query_terms: dict[str, int],
) -> dict[str, dict]:
    """Retrieve documents containing at least one query term.

    No relevance scores are calculated at this stage.
    """

    candidates = {}

    for term, query_frequency in query_terms.items():
        term_info = index.get_term(term)

        # Ignore terms that are absent from the index.
        if term_info is None:
            continue

        postings = index.get_postings(term)

        for posting in postings:
            app_id = posting["app_id"]

            if app_id not in candidates:
                candidates[app_id] = {
                    "document": {
                        "app_id": app_id,
                        "game_title": posting["game_title"],
                    },
                    "matched_terms": {},
                }

            candidates[app_id]["matched_terms"][term] = {
                "query_frequency": query_frequency,
                "term_frequency": posting["term_frequency"],
                "document_frequency": term_info["document_frequency"],
            }

    return candidates


def iter_candidates_with_document_terms(
    index,
    candidates: dict[str, dict],
) -> Iterator[tuple[str, dict]]:
    """Yield candidates enriched with their complete document terms."""

    for app_id, candidate in candidates.items():
        document_terms = index.get_document_terms(app_id)

        enriched_candidate = {
            **candidate,
            "document_terms": {
                item["term"]: {
                    "term_frequency": item["term_frequency"],
                    "document_frequency": item["document_frequency"],
                }
                for item in document_terms
            },
        }

        yield app_id, enriched_candidate
