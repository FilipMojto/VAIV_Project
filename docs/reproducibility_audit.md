# Reproducibility audit — repository state on 20 November 2026

## 1. Purpose and scope

This document records the Phase 3.2 reproducibility audit. It distinguishes implemented project workflows from development environments that have only been installed or smoke-tested. It describes the repository and local environment as inspected on 20 November 2026; it does not claim that the entire project has been reproduced from a fresh machine.

The audit covered BGG collection and parsing, dataset validation and inspection, the custom Python indexer, Spark/Wikipedia, PyLucene, Python dependencies and the native toolchain.

## 2. Verified development environment

The recorded WSL environment is:

| Component | Version / configuration |
|---|---|
| Operating environment | WSL 2, Ubuntu 26.04 / Resolute |
| Python | 3.11.18 in `.venv-wsl` |
| Java | OpenJDK 17.0.21.1 |
| Apache Ant | 1.10.15 |
| JCC | 3.14, non-shared build |
| PyLucene | 9.12.0 |
| PySpark | 4.3.0 |

The Spark and PyLucene smoke tests passed in this environment. The PyLucene native build additionally required JDK development headers/JNI libraries, C/C++ build tools and Python 3.11 development headers. The build variables and instructions are recorded in `docs/reproduction.md`.

The active `.venv-wsl` inspected during the audit did not contain the packages declared in `requirements.txt`: Playwright, tqdm, pandas, tiktoken, pytest, cloudscraper or curl_cffi. It did contain PySpark 4.3.0, PyLucene 9.12.0 and JCC 3.14. `requests`, used by an auxiliary experiment, was also absent and is not declared in `requirements.txt`.

`pip check` reported no broken requirements among installed packages. This does not establish that every package in `requirements.txt` is installed; the separate requirements-versus-installed check identified the missing packages.

`JAVA_HOME` was not set in the shell used for the audit, although Java and Ant were available. The documented `JAVA_HOME` value was used during the successful native build. It should be treated as a build-environment setting, not as proof that it is permanently configured in every shell.

## 3. Python dependency audit

The repository has one dependency manifest: `requirements.txt`. It uses minimum-version constraints rather than exact pins. There is no `pyproject.toml`, `uv.lock`, `Pipfile`, `Pipfile.lock` or `environment.yml`.

| Package | Use found in the repository | Audit finding |
|---|---|---|
| `playwright` | BGG crawling and older scraping utilities | Required for live browser/CDP crawling |
| `tqdm` | Crawler and scraping progress display | Used by the main crawler |
| `pytest` | `testing/test_parsing.py` | Test dependency; absent from audited environment |
| `pandas` | Dataset-inspection experiment | Experiment/demo dependency |
| `tiktoken` | Token-analysis experiment | Experiment/demo dependency |
| `requests` | `experiments/teststeam.py` | Used by an auxiliary experiment but undeclared |
| `cloudscraper` | No imports found | Marked as legacy in `requirements.txt` |
| `curl_cffi` | No imports found | Marked as legacy in `requirements.txt` |

Imports from `src` are internal project modules, not third-party dependencies. PySpark, PyLucene and JCC are separate environment components and are not declared in `requirements.txt`.

The project should eventually choose one authoritative dependency-management workflow. For now, `requirements.txt` is the only repository dependency manifest, but it is not a complete, pinned description of every environment component needed for all project activities.

## 4. Existing workflows and reproducibility

### 4.1 BGG crawler and HTML cache

The crawler is implemented in `src/crawler.py`, with browser access handled by `src/crawling.py`.

- It starts from five hard-coded seed game IDs and discovers linked IDs from captured BGG HTML.
- It checks `data/bgg_raw_htmls/{app_id}.html` before attempting a live fetch.
- If usable cached HTML is unavailable, Playwright connects to an already running Chrome instance through the configured CDP endpoint, `http://localhost:9222`. The crawler does not launch its own browser.
- Live crawling requires network access, Chrome with remote debugging enabled and, when challenged, manual Cloudflare clearance. The Chrome startup instructions are in `docs/startchrome.md`.
- The main external Python dependencies are Playwright and tqdm. Connecting to an externally launched Chrome through CDP does not require Playwright to download and launch its own Chromium browser.

The crawler writes TSV data, timestamped snapshots, a temporary TSV and a JSON crawl-state file under `data/bgg_games/`. The raw HTML cache is separate. The TSV preserves collected records; the JSON state preserves traversal progress, including queue/visited state and interruption information. Keeping only the TSV does not preserve the exact crawl position. If the state file is absent, traversal starts again from the seed IDs, although existing TSV records are upserted by `app_id`.

The crawler and cache workflow are implemented, but a fresh end-to-end crawl was not performed during this audit. Live reproducibility depends on BGG availability, browser configuration and challenge handling.

### 4.2 Parsing and parser tests

The parser is implemented in `src/parsing.py`. `testing/test_parsing.py` uses 24 captured HTML fixtures under `testing/fixtures/`, so it does not require a live browser or network connection.

A direct verification run successfully parsed a game title from all 24 fixtures. This was not a formal pytest run. The fixtures matched the corresponding local HTML cache files byte-for-byte during the audit. Their total size was approximately 13.68 MiB.

The parser-test changes were committed locally in `ea231a5` (`test: make parser tests independent of live BGG`). Formal execution through pytest was not verified because pytest was absent from the audited `.venv-wsl`. The direct fixture verification passed, but a successful pytest run in the supported environment remains to be recorded.

The fixtures are intentionally committed so parser tests can run independently of the mutable live website and external cache. They are not a complete snapshot of BGG or proof that every parser field is correct for every game.

### 4.3 Dataset validation and inspection

`experiments/testdata.py` provides TSV validation checks. Dataset inspection was also performed using scripts under `experiments/dataanalysis/`.

The selected snapshot is `data/bgg_games/bgg_games_20261025_113653.tsv`:

- 17,652 data rows;
- 43 columns;
- 17,648 distinct `app_id` values;
- four duplicated IDs, each occurring twice;
- each duplicated pair is identical across all 43 columns.

The duplicated IDs are 13, 266192, 30549 and 822. The controlled retrieval experiment should use one row per `app_id`, giving 17,648 unique game records. Preserve the original TSV unchanged and document deterministic deduplication in the experiment pipeline.

The inspection identified anomalous source values in some numeric-looking fields, including unusually high player counts and play times. Some unusual values were confirmed to be displayed on the source BGG pages. Preserve raw values and report anomalies rather than silently correcting them. The `age` field contains values such as `10+` and should not be treated as a simple numeric field without a deliberate parsing rule.

The dataset contains identity, descriptive text, game classifications, contributor names, numeric attributes, popularity/activity measures, awards and relationship fields. Several list-like columns are serialized as Python-like text, and missing values vary by field. These findings inform field selection and preprocessing; they do not justify treating every column as searchable text.

### 4.4 Custom Python indexer

`src/indexers.py` contains the current `BGGIndexer`. It reads the TSV, skips rows without an `app_id`, combines selected textual fields, tokenizes them with a regular expression, builds an in-memory inverted index and stores per-document term frequencies.

The index is constructed in memory from the selected TSV each time the indexer is invoked. It is not persisted to disk and is not updated incrementally: any change to the input data requires a full rebuild, and the index does not survive the end of the process.

The tokenizer is `re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())`. It is restricted to ASCII alphabetic tokens of at least three characters. The current term frequency is natural/raw TF. Two IDF variants are implemented:

- Classic IDF: `log(N / df)`.
- Smoothed IDF: `log((N + 1) / (df + 1)) + 1`.

The score is the sum of TF × IDF contributions for query terms. There is no document-length normalization, field-specific weighting, phrase matching or BM25 implementation in this custom indexer. It is a baseline, not the final selected retrieval model.

The module currently combines reusable indexing code with command-line parsing and logging setup at import time. This is a known refactoring concern for a later phase. No indexer changes were made during this audit.

### 4.5 PySpark and Wikipedia

PySpark 4.3.0 was installed and its local runtime was smoke-tested successfully using `local[2]` and `spark.range(5)`. This verifies basic local Spark execution only.

A Wikipedia dump exists locally at `data/wiki/enwiki-latest-pages-articles.xml.bz2`, but the dump is ignored by Git. Its rolling `latest` filename does not identify a fixed release. The checksum operation was not completed during the audit. The inspected excerpt from `data/logs/wiki_extraction.log` records BGG parsing diagnostics, including parsed JSON and corresponding HTML snippets for Catan; it does not establish that a Wikipedia extraction pipeline ran.

No project source implementing Wikipedia dump parsing, regex extraction, Spark processing, the BGG join or output reporting was found in the audited repository. The Spark/Wikipedia pipeline must therefore be classified as **not implemented or not present in the audited repository**, rather than as a reproducible workflow.

If the dump is used in a future implementation, record its exact source, fixed release/date, download date, checksum and path. A fixed input version is necessary for meaningful reproduction.

### 4.6 PyLucene

PyLucene 9.12.0 was built and installed using JCC 3.14 and OpenJDK 17. The in-memory smoke test documented in `docs/reproduction.md` initialized the JVM, created a `ByteBuffersDirectory`, indexed one short sentence and retrieved one hit for the query `strategy`.

The audit found no project-level Lucene API usage, no BGG-specific Lucene schema or query implementation, and no persistent project index in the repository. The smoke test verifies the native bridge and basic Lucene API only. Project indexing, field mapping, analyzers, Boolean/range/phrase/fuzzy queries and ranking comparisons remain future work.

## 5. Data and generated artifacts

The main BGG TSV snapshots, HTML cache, Wikipedia dump and local logs are data artifacts rather than source code. The inspected `data/wiki/` and `data/logs/` directories are ignored by Git. Generated Spark output directories and Lucene indexes should also remain outside version control unless a small test fixture is intentionally committed.

The parser HTML fixtures are an exception by design: they are stable test inputs committed under `testing/fixtures/` so parser tests can run offline.

## 6. Current reproduction boundary

| Activity | Verified or currently reproducible | Not established |
|---|---|---|
| Python environment | A working recorded Python 3.11 environment exists | Fully pinned fresh installation of all project dependencies |
| Spark | Local Spark smoke test | Wikipedia extraction, BGG join and reporting pipeline |
| PyLucene | Native build and in-memory indexing/search smoke test | Persistent BGG index, project schema and required query types |
| BGG parser | Offline parsing against 24 committed fixtures | Full coverage of all BGG page variants |
| BGG crawler | Source workflow, cache and resume mechanisms inspected | Fresh end-to-end crawl under a clean environment |
| Dataset | Selected snapshot inspected and duplicate policy identified | Automated, versioned experiment-preparation pipeline |
| Custom indexer | Natural-TF/classic-and-smoothed-IDF baseline inspected | Final weighting configuration and controlled evaluation |

This audit closes the investigation of the repository's current reproducibility state. It does not claim that the full course project is complete. The next activity is the controlled mathematical TF/IDF experiment described in the project roadmap.
