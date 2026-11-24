"""Search an existing BGG Lucene index using supported query types."""

import argparse
from pathlib import Path

from src.lucene.search import LuceneSearcher

DEFAULT_INDEX_ROOT = Path("data/indexes/lucene_updated")

INDEX_NAMES = {
    "bgg_only": "lucene_bgg",
    "enriched": "lucene_enriched",
}

TEXT_FIELD_DEFAULT = "bgg_all_text"
TITLE_FIELD_DEFAULT = "game_title"
RANGE_FIELD_DEFAULT = "release_year"


def format_wiki_value(field: str, value) -> list[str]:
    """Format selected Wikipedia attributes for readable terminal output."""
    if value in (None, ""):
        return ["—"]

    if field == "wiki_publisher":
        # Handle both newline-separated and inline Markdown-style lists.
        publishers = []

        for line in value.splitlines():
            for item in line.split("*"):
                item = item.strip().lstrip("-").strip()

                if item:
                    publishers.append(item)

        return publishers or ["—"]

    if field == "wiki_number_of_players":
        return [
            item.strip()
            for item in value.split("|")
            if item.strip()
        ] or ["—"]

    return [str(value)]


def search(
    index_path: Path,
    mode: str,
    query: str | None = None,
    field: str | None = None,
    operator: str = "OR",
    lower: int | None = None,
    upper: int | None = None,
    max_edits: int = 2,
    limit: int = 10,
):
    """Execute one supported query against an existing Lucene index."""

    if limit <= 0:
        raise ValueError("limit must be positive.")

    with LuceneSearcher(index_path) as searcher:
        if mode == "text":
            if not query:
                raise ValueError("A query is required for text search.")

            return searcher.search_text(
                query,
                field=field or TEXT_FIELD_DEFAULT,
                operator=operator,
                limit=limit,
            )

        if mode == "phrase":
            if not query:
                raise ValueError("A phrase is required.")

            return searcher.search_phrase(
                query,
                field=field or TITLE_FIELD_DEFAULT,
                limit=limit,
            )

        if mode == "fuzzy":
            if not query:
                raise ValueError("A term is required for fuzzy search.")

            return searcher.search_fuzzy(
                query,
                field=field or TITLE_FIELD_DEFAULT,
                max_edits=max_edits,
                limit=limit,
            )

        if mode == "range":
            if lower is None or upper is None:
                raise ValueError(
                    "Both --lower and --upper are required for range search."
                )

            return searcher.search_range(
                field=field or RANGE_FIELD_DEFAULT,
                lower=lower,
                upper=upper,
                limit=limit,
            )

    raise ValueError(f"Unsupported search mode: {mode}")


def main():
    parser = argparse.ArgumentParser(description="Search an existing BGG Lucene index.")

    parser.add_argument(
        "query",
        nargs="?",
        help="Search text, phrase or fuzzy term. Not required for range mode.",
    )
    parser.add_argument(
        "--index",
        choices=INDEX_NAMES,
        default="bgg_only",
        help="Index to search: bgg_only or enriched.",
    )
    parser.add_argument(
        "--index-root",
        type=Path,
        default=DEFAULT_INDEX_ROOT,
        help=f"Directory containing both indexes. Defaults to {DEFAULT_INDEX_ROOT}.",
    )
    parser.add_argument(
        "--mode",
        choices=("text", "phrase", "fuzzy", "range"),
        default="text",
        help="Query type (default: text).",
    )
    parser.add_argument(
        "--field",
        help=(
            "Lucene field. Defaults: bgg_all_text for text, "
            "game_title for phrase/fuzzy, release_year for range."
        ),
    )
    parser.add_argument(
        "--operator",
        choices=("AND", "OR"),
        default="OR",
        help="Boolean operator for text search (default: OR).",
    )
    parser.add_argument(
        "--lower",
        type=int,
        help="Inclusive lower bound for numeric range search.",
    )
    parser.add_argument(
        "--upper",
        type=int,
        help="Inclusive upper bound for numeric range search.",
    )
    parser.add_argument(
        "--max-edits",
        type=int,
        choices=(0, 1, 2),
        default=2,
        help="Maximum edit distance for fuzzy search (default: 2).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of results (default: 10).",
    )

    args = parser.parse_args()

    if args.limit <= 0:
        parser.error("--limit must be positive.")

    if args.mode != "range" and not args.query:
        parser.error("A query is required unless --mode range is used.")

    if args.mode == "range":
        if args.lower is None or args.upper is None:
            parser.error("Range mode requires both --lower and --upper.")

    index_path = args.index_root / INDEX_NAMES[args.index]

    try:
        response = search(
            index_path=index_path,
            mode=args.mode,
            query=args.query,
            field=args.field,
            operator=args.operator,
            lower=args.lower,
            upper=args.upper,
            max_edits=args.max_edits,
            limit=args.limit,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    print("\n=== LUCENE BGG SEARCH ===")
    print(f"Index: {index_path}")
    print(f"Mode: {args.mode}")

    if args.mode == "range":
        print(
            f"Range: {args.field or RANGE_FIELD_DEFAULT} "
            f"[{args.lower}, {args.upper}]"
        )
    else:
        print(f"Query: {args.query}")
        print(
            f"Field: {args.field or (TEXT_FIELD_DEFAULT if args.mode == 'text' else TITLE_FIELD_DEFAULT)}"
        )

    if args.mode == "text":
        print(f"Boolean operator: {args.operator}")

    if args.mode == "fuzzy":
        print(f"Maximum edits: {args.max_edits}")

    print(f"Total hits: {response['total_hits']:,}")

    results = response["results"]

    if not results:
        print("\nNo matching games found.")
        return

    print(f"\n=== TOP {len(results)} RESULTS ===")

    for rank, result in enumerate(results, start=1):
        # Show the actual value used by a numeric range query.
        if args.mode == "range":
            distinguishing_attribute = (
                f"{args.field or RANGE_FIELD_DEFAULT}: "
                f"{result.get(args.field or RANGE_FIELD_DEFAULT) or '—'}"
            )
        else:
            distinguishing_attribute = (
                f"BGG release year: {result.get('release_year') or '—'}"
            )

        print(
            f"\n{rank:>2}. {result['game_title']} "
            f"(BGG ID: {result['app_id']}, "
            f"{distinguishing_attribute}, "
            f"score: {result['score']:.4f})"
        )

        # Show all stored Wikipedia attributes for enriched-index results.
        if args.index == "enriched":
            print("    Wikipedia enrichment:")

            for field in LuceneSearcher.WIKI_FIELDS:
                value = result.get(field)
                formatted_values = format_wiki_value(field, value)

                if field in ("wiki_publisher", "wiki_number_of_players"):
                    print(f"      {field}:")
                    for item in formatted_values:
                        print(f"        - {item}")
                else:
                    print(f"      {field}: {formatted_values[0]}")


if __name__ == "__main__":
    main()
