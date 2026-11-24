
"""Search persistent board-game indexes using Apache Lucene."""

from pathlib import Path

import lucene


class LuceneSearcher:
    """Search a persistent Lucene board-game index."""

    NUMERIC_FIELDS = {
        "release_year",
        "num_of_players_min",
        "num_of_players_max",
        "play_time_min",
        "play_time_max",
    }

    WIKI_FIELDS = (
        "wiki_short_description",
        "wiki_designer",
        "wiki_publisher",
        "wiki_number_of_players",
        "wiki_playing_time",
        "wiki_publication_history",
        "wiki_setup_time",
        "wiki_chance",
        "wiki_official_website",
        "wiki_infobox_type",
        "wiki_candidate_score",
        "wiki_matched_page_id",
        "wiki_matched_title",
        "wiki_page_id",
        "wiki_title",
        "wiki_release_date",
        "wiki_matched_variant_type",
        "wiki_redirect_status",
    )

    def __init__(self, index_path: str | Path):
        # Initialize the JVM before using Lucene classes.
        if lucene.getVMEnv() is None:
            lucene.initVM()

        from java.nio.file import Paths
        from org.apache.lucene.store import FSDirectory
        from org.apache.lucene.index import DirectoryReader
        from org.apache.lucene.search import IndexSearcher
        from src.lucene.analyzer import create_analyzer

        self.index_path = Path(index_path)

        if not self.index_path.exists():
            raise FileNotFoundError(
                f"Lucene index does not exist: {self.index_path}"
            )

        self.directory = FSDirectory.open(
            Paths.get(str(self.index_path.resolve()))
        )
        self.reader = DirectoryReader.open(self.directory)
        self.searcher = IndexSearcher(self.reader)

        from org.apache.lucene.search.similarities import BM25Similarity

        self.searcher.setSimilarity(BM25Similarity(1.2, 0.75))
        self.analyzer = create_analyzer()

    @property
    def document_count(self) -> int:
        """Return the number of indexed documents."""
        return self.reader.numDocs()

    def _parse_text_query(
        self,
        query_text: str,
        field: str,
        operator: str = "OR",
    ):
        """Parse text using the configured field and Boolean operator."""
        from org.apache.lucene.queryparser.classic import QueryParser

        if not query_text.strip():
            raise ValueError("Query must not be empty.")

        parser = QueryParser(field, self.analyzer)

        operator = operator.upper()

        if operator == "AND":
            parser.setDefaultOperator(QueryParser.Operator.AND)
        elif operator == "OR":
            parser.setDefaultOperator(QueryParser.Operator.OR)
        else:
            raise ValueError("Operator must be 'AND' or 'OR'.")

        return parser.parse(query_text)

    def _format_results(self, top_docs):
        """Convert Lucene hits into ordinary Python dictionaries."""
        results = []

        for hit in top_docs.scoreDocs:
            document = self.searcher.doc(hit.doc)

            result = {
                "app_id": document.get("app_id"),
                "game_title": document.get("game_title"),
                "score": round(hit.score, 4),
            }

            # Retrieve stored BGG numeric attributes.
            for field in self.NUMERIC_FIELDS:
                result[field] = document.get(field)

            # Retrieve stored Wikipedia attributes when available.
            for field in self.WIKI_FIELDS:
                result[field] = document.get(field)

            results.append(result)

        return {
            "total_hits": top_docs.totalHits.value,
            "results": results,
        }

    def search_text(
        self,
        query_text: str,
        field: str = "game_title",
        operator: str = "OR",
        limit: int = 10,
    ):
        """Search analyzed text using AND or OR semantics."""
        query = self._parse_text_query(
            query_text,
            field,
            operator,
        )

        top_docs = self.searcher.search(query, limit)
        return self._format_results(top_docs)

    def search_phrase(
        self,
        phrase: str,
        field: str = "game_title",
        limit: int = 10,
    ):
        """Search for an exact sequence of analyzed terms."""
        from org.apache.lucene.queryparser.classic import QueryParser

        if not phrase.strip():
            raise ValueError("Phrase must not be empty.")

        parser = QueryParser(field, self.analyzer)
        escaped_phrase = QueryParser.escape(phrase)

        query = parser.parse(f'"{escaped_phrase}"')
        top_docs = self.searcher.search(query, limit)

        return self._format_results(top_docs)

    def search_fuzzy(
        self,
        term: str,
        field: str = "game_title",
        max_edits: int = 2,
        limit: int = 10,
    ):
        """Search for terms similar to the supplied term."""
        from org.apache.lucene.index import Term
        from org.apache.lucene.search import FuzzyQuery
        from org.apache.lucene.analysis.tokenattributes import CharTermAttribute

        if not term.strip():
            raise ValueError("Term must not be empty.")

        if max_edits not in (0, 1, 2):
            raise ValueError("max_edits must be 0, 1, or 2.")

        # Use the analyzer to normalize the input term.
        token_stream = self.analyzer.tokenStream(field, term)
        term_attribute = token_stream.addAttribute(
            CharTermAttribute.class_
        )

        tokens = []

        try:
            token_stream.reset()

            while token_stream.incrementToken():
                tokens.append(str(term_attribute.toString()))

            token_stream.end()
        finally:
            token_stream.close()

        if not tokens:
            return {"total_hits": 0, "results": []}

        # FuzzyQuery operates on individual terms.
        query = FuzzyQuery(
            Term(field, tokens[0]),
            max_edits,
        )

        top_docs = self.searcher.search(query, limit)
        return self._format_results(top_docs)

    def search_range(
        self,
        field: str,
        lower: int,
        upper: int,
        limit: int = 10,
    ):
        """Search an inclusive numeric range."""
        from org.apache.lucene.document import IntPoint

        if field not in self.NUMERIC_FIELDS:
            raise ValueError(
                f"Unsupported numeric field: {field}"
            )

        if lower > upper:
            raise ValueError("Lower bound must not exceed upper bound.")

        query = IntPoint.newRangeQuery(
            field,
            int(lower),
            int(upper),
        )

        top_docs = self.searcher.search(query, limit)
        return self._format_results(top_docs)

    def close(self):
        """Release Lucene resources."""
        self.analyzer.close()
        self.reader.close()
        self.directory.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
