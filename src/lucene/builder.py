
"""Build persistent Lucene indexes from the enriched BGG Parquet dataset."""

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path

import lucene

from pyspark.sql import SparkSession

from java.nio.file import Paths

from src.lucene.analyzer import create_analyzer
from org.apache.lucene.document import (
    Document,
    Field,
    IntPoint,
    StoredField,
    StringField,
    TextField,
)
from org.apache.lucene.index import (
    DirectoryReader,
    IndexWriter,
    IndexWriterConfig,
)
from org.apache.lucene.store import FSDirectory


BGG_TEXT_FIELDS = (
    "game_title",
    "alternate_names",
    "short_description",
    "description",
    "game_type",
    "game_category",
    "game_mechanic",
    "game_family",
    "designer",
    "publisher",
    "awards_honors",
)

BGG_NUMERIC_FIELDS = (
    "release_year",
    "num_of_players_min",
    "num_of_players_max",
    "play_time_min",
    "play_time_max",
)

WIKI_TEXT_FIELDS = (
    "wiki_short_description",
    "wiki_designer",
    "wiki_publisher",
    "wiki_number_of_players",
    "wiki_playing_time",
)

WIKI_STORED_FIELDS = (
    "wiki_matched_page_id",
    "wiki_matched_title",
    "wiki_page_id",
    "wiki_title",
    "wiki_release_date",
    "wiki_matched_variant_type",
    "wiki_redirect_status",
)

WIKI_REQUIRED_FIELDS = (
    *WIKI_TEXT_FIELDS,
    *WIKI_STORED_FIELDS,
    "wiki_infobox_type",
    "wiki_candidate_score",
)

DEFAULT_SOURCE = Path("data/wiki_extracted/bgg_wikipedia_enriched")
DEFAULT_INDEX_ROOT = Path("data/indexes")


class LuceneIndexBuilder:
    """Build BGG-only and BGG+Wikipedia Lucene indexes."""

    def __init__(self):
        # This builder is intended to run in a fresh Python process.
        lucene.initVM()

    @staticmethod
    def _get_text(value):
        """Return a stripped string or an empty string."""

        if value is None:
            return ""

        return str(value).strip()

    @staticmethod
    def _add_numeric_field(document, field_name, value, app_id):
        """Add an indexed and stored integer field when populated."""

        text = LuceneIndexBuilder._get_text(value)

        if not text:
            return

        if not re.fullmatch(r"[0-9]+", text):
            raise ValueError(
                f"Invalid integer in {field_name} for app_id "
                f"{app_id}: {text!r}"
            )

        number = int(text)

        document.add(IntPoint(field_name, number))
        document.add(StoredField(field_name, number))

    @classmethod
    def _build_document(cls, record, include_wikipedia):
        """Convert one Spark row into a Lucene document."""

        document = Document()

        app_id = cls._get_text(record["app_id"])
        game_title = cls._get_text(record["game_title"])

        if not app_id.isdigit() or int(app_id) <= 0:
            raise ValueError(f"Invalid app_id: {app_id!r}")

        if not game_title:
            raise ValueError(f"Missing game_title for app_id {app_id}")

        document.add(
            StringField("app_id", app_id, Field.Store.YES)
        )

        combined_text = " ".join(
            cls._get_text(record[field_name])
            for field_name in BGG_TEXT_FIELDS
        )

        document.add(
            TextField(
                "bgg_all_text",
                combined_text,
                Field.Store.NO,
            )
        )

        for field_name in BGG_TEXT_FIELDS:
            value = cls._get_text(record[field_name])

            if not value:
                continue

            store = (
                Field.Store.YES
                if field_name == "game_title"
                else Field.Store.NO
            )

            document.add(
                TextField(field_name, value, store)
            )

        for field_name in BGG_NUMERIC_FIELDS:
            cls._add_numeric_field(
                document,
                field_name,
                record[field_name],
                app_id,
            )

        if include_wikipedia:
            for field_name in WIKI_TEXT_FIELDS:
                value = cls._get_text(record[field_name])

                if value:
                    document.add(
                        TextField(field_name, value, Field.Store.YES)
                    )

            infobox_type = cls._get_text(
                record["wiki_infobox_type"]
            )

            if infobox_type:
                document.add(
                    StringField(
                        "wiki_infobox_type",
                        infobox_type,
                        Field.Store.YES,
                    )
                )

            for field_name in WIKI_STORED_FIELDS:
                value = cls._get_text(record[field_name])

                if value:
                    document.add(
                        StoredField(field_name, value)
                    )

            candidate_score = record["wiki_candidate_score"]

            if candidate_score is not None:
                document.add(
                    StoredField(
                        "wiki_candidate_score",
                        int(candidate_score),
                    )
                )

        return document

    @staticmethod
    def _validate_index(index_path, expected_count):
        """Reopen a completed index and verify its document count."""

        directory = FSDirectory.open(Paths.get(str(index_path)))

        try:
            reader = DirectoryReader.open(directory)

            try:
                actual_count = reader.numDocs()

                if actual_count != expected_count:
                    raise RuntimeError(
                        f"Unexpected document count in {index_path}: "
                        f"expected {expected_count}, got {actual_count}"
                    )

                return actual_count

            finally:
                reader.close()

        finally:
            directory.close()

    def build(
        self,
        source_path=DEFAULT_SOURCE,
        index_root=DEFAULT_INDEX_ROOT,
    ):
        """Build both indexes and validate their persistence."""

        source_path = Path(source_path)
        index_root = Path(index_root)

        if not source_path.is_dir():
            raise FileNotFoundError(
                f"Parquet source does not exist: {source_path}"
            )

        index_root.mkdir(parents=True, exist_ok=True)

        bgg_target = index_root / "lucene_bgg"
        enriched_target = index_root / "lucene_enriched"

        targets = (bgg_target, enriched_target)

        # Never overwrite an existing index implicitly.
        existing = [str(path) for path in targets if path.exists()]

        if existing:
            raise FileExistsError(
                "Index destination already exists. Remove or rename "
                f"it before rebuilding: {existing}"
            )

        bgg_temp = Path(
            tempfile.mkdtemp(prefix=".lucene_bgg.", dir=index_root)
        )
        enriched_temp = Path(
            tempfile.mkdtemp(prefix=".lucene_enriched.", dir=index_root)
        )

        spark = None
        bgg_directory = None
        enriched_directory = None
        bgg_writer = None
        enriched_writer = None
        bgg_analyzer = None
        enriched_analyzer = None

        try:
            spark = (
                SparkSession.builder
                .appName("BGGLuceneIndexBuilder")
                .master("local[*]")
                .getOrCreate()
            )

            dataframe = spark.read.parquet(str(source_path))

            required_fields = (
                "app_id",
                *BGG_TEXT_FIELDS,
                *BGG_NUMERIC_FIELDS,
                *WIKI_REQUIRED_FIELDS,
            )

            missing_fields = sorted(
                set(required_fields) - set(dataframe.columns)
            )

            if missing_fields:
                raise ValueError(
                    f"Parquet dataset is missing fields: {missing_fields}"
                )

            print("=== BUILDING LUCENE INDEXES ===")
            print(f"Source: {source_path}")

            bgg_directory = FSDirectory.open(
                Paths.get(str(bgg_temp))
            )
            enriched_directory = FSDirectory.open(
                Paths.get(str(enriched_temp))
            )

            bgg_analyzer = create_analyzer()
            enriched_analyzer = create_analyzer()

            bgg_config = IndexWriterConfig(bgg_analyzer)
            bgg_config.setOpenMode(
                IndexWriterConfig.OpenMode.CREATE
            )

            enriched_config = IndexWriterConfig(enriched_analyzer)
            enriched_config.setOpenMode(
                IndexWriterConfig.OpenMode.CREATE
            )

            bgg_writer = IndexWriter(
                bgg_directory,
                bgg_config,
            )
            enriched_writer = IndexWriter(
                enriched_directory,
                enriched_config,
            )

            document_count = 0
            seen_ids = set()

            for row in dataframe.toLocalIterator():
                record = row.asDict(recursive=False)

                app_id = self._get_text(record["app_id"])

                if app_id in seen_ids:
                    raise ValueError(
                        f"Duplicate app_id encountered: {app_id}"
                    )

                seen_ids.add(app_id)

                bgg_document = self._build_document(
                    record,
                    include_wikipedia=False,
                )

                enriched_document = self._build_document(
                    record,
                    include_wikipedia=True,
                )

                bgg_writer.addDocument(bgg_document)
                enriched_writer.addDocument(enriched_document)

                document_count += 1

                if document_count % 2000 == 0:
                    print(
                        f"Indexed {document_count:,} documents..."
                    )

            if document_count == 0:
                raise ValueError("Parquet dataset contains no records.")

            # Commit both indexes before closing them.
            bgg_writer.commit()
            enriched_writer.commit()

            print("\n=== BUILD COMPLETE ===")
            print(f"Documents indexed: {document_count:,}")

        finally:
            if bgg_writer is not None:
                bgg_writer.close()

            if enriched_writer is not None:
                enriched_writer.close()

            if bgg_analyzer is not None:
                bgg_analyzer.close()

            if enriched_analyzer is not None:
                enriched_analyzer.close()

            if bgg_directory is not None:
                bgg_directory.close()

            if enriched_directory is not None:
                enriched_directory.close()

            if spark is not None:
                spark.stop()

        try:
            # Verify the indexes while they are still in temporary folders.
            bgg_count = self._validate_index(
                bgg_temp,
                document_count,
            )

            enriched_count = self._validate_index(
                enriched_temp,
                document_count,
            )

            # Publish only after both indexes have passed validation.
            bgg_temp.rename(bgg_target)
            enriched_temp.rename(enriched_target)

        except Exception:
            shutil.rmtree(bgg_temp, ignore_errors=True)
            shutil.rmtree(enriched_temp, ignore_errors=True)
            raise

        result = {
            "source": str(source_path),
            "document_count": document_count,
            "bgg_index": str(bgg_target),
            "bgg_document_count": bgg_count,
            "enriched_index": str(enriched_target),
            "enriched_document_count": enriched_count,
        }

        print("\n=== PERSISTENT INDEX VALIDATION ===")
        print(json.dumps(result, indent=4))

        return result


def main():
    parser = argparse.ArgumentParser(
        description="Build persistent BGG Lucene indexes."
    )

    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
    )

    parser.add_argument(
        "--index-root",
        type=Path,
        default=DEFAULT_INDEX_ROOT,
    )

    args = parser.parse_args()

    builder = LuceneIndexBuilder()

    builder.build(
        source_path=args.source,
        index_root=args.index_root,
    )


if __name__ == "__main__":
    main()
