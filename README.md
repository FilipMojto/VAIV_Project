# VINF Project — BoardGameGeek Search Engine

This repository contains an information-retrieval project developed for the VINF (Vyhľadávanie informácií) course at the Faculty of Informatics and Information Technologies (FIIT).

The project builds a searchable collection of BoardGameGeek (BGG) board-game records. It combines a custom Python retrieval baseline with distributed data processing using Apache Spark and a Lucene-based search implementation through PyLucene. The aim is not only to build a working search engine, but also to explain and evaluate the indexing and ranking decisions made during the project.

## Project components

- **BGG data collection:** crawling and extracting board-game metadata into a tab-separated dataset.
- **Custom Python indexer:** an inverted index with term-frequency statistics and TF-IDF-based ranking. It serves as the transparent baseline for experiments.
- **Wikipedia enrichment:** planned/ongoing Spark processing of a Wikipedia XML dump, extraction of relevant pages, and joining enriched information with BGG records.
- **Lucene search:** PyLucene integration for a production-style inverted index and retrieval features such as Boolean, phrase, range and fuzzy queries, plus BM25 ranking.
- **Evaluation:** comparison of ranking approaches using a shared set of queries and relevance judgments, followed by comparison with external search results where required by the course.

The current implementation status is recorded in [`docs/project_status_and_roadmap.md`](docs/project_status_and_roadmap.md). The lecture concepts relevant to term weighting and normalization are summarized in [`docs/lecture_06_retrieval_weighting.md`](docs/lecture_06_retrieval_weighting.md).

## Repository layout

The exact layout may evolve as the project develops. The main areas currently include:

- `src/` — Python source code, including BGG crawling, configuration and the custom indexer.
- `data/` — input and generated datasets. Large datasets, raw HTML, archives and generated indexes are intentionally excluded from Git.
- `docs/` — project documentation, implementation status, lecture notes and reproduction instructions.
- `experiments/` — temporary or exploratory experiments; only retain files that are useful and intentionally maintained.

## Environment and reproducibility

The verified development environment used for the current Spark and Lucene milestones is:

- Ubuntu under WSL 2 (Ubuntu 26.04 / Resolute at the time of setup)
- Python 3.11.18
- OpenJDK 17
- Apache Spark / PySpark 4.3.0
- PyLucene 9.12.0
- JCC 3.14
- Apache Ant 1.10.15

See [`docs/reproduction.md`](docs/reproduction.md) for the environment setup, PyLucene build notes, smoke tests and data requirements.

### Python dependencies

`requirements.txt` is a pip-compatible list of dependencies; it is not automatically synchronized by every Python environment manager. If the project adopts `uv` or Pipenv as its dependency source of truth, dependencies should be declared in `pyproject.toml` or `Pipfile` and locked with the corresponding tool. A `requirements.txt` can then be exported/generated when needed for compatibility. See the dependency-management section in the reproduction guide before changing the project's dependency workflow.

PyLucene is a special case: it requires a compatible Java/JCC toolchain and a native extension build. It should not be documented as though a plain `pip install -r requirements.txt` can reliably install it on every machine.

## Current limitations and next steps

The custom indexer is intentionally a simple baseline. Its current scoring uses raw term frequency and classic or smoothed IDF, without document-length normalization or field-specific weighting. The next retrieval-model phase will evaluate lecture-covered TF and IDF variants before choosing a small, defensible set of methods for the custom indexer. BM25 will be evaluated separately through Lucene rather than duplicated in the baseline without a clear experimental reason.

The project plan and completion state are maintained in [`docs/project_status_and_roadmap.md`](docs/project_status_and_roadmap.md).
