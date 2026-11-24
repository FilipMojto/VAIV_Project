# Project Architecture

## 1. Purpose of this document

This document provides an overview of the project's structure and explains how its main components and subcomponents fit together.

Its purpose is to help a reader navigate the repository and understand:

- where the main functionality is implemented;
- which module is responsible for each part of the system;
- how data moves between the main components;
- where to find the entry points for building indexes, searching, and running experiments;
- where tests, documentation, source data, and generated data are kept.

The project is organised around three main technical components:

1. **SQLite indexing and retrieval** – the baseline indexing and search implementation.
2. **Wikipedia extraction and enrichment using Spark** – the distributed data-processing component.
3. **Lucene indexing and retrieval** – the second indexing and search implementation, including BGG-only and enriched indexes.

The `experiments` directory contains retrieval experiments and evaluation workflows built around these components. It is not a replacement for the core implementations in `src`.

This document focuses on project organisation and responsibilities rather than experimental findings, evaluation results, dataset statistics, or detailed algorithm explanations.

---

## 2. Repository at a glance

The following tree highlights the main parts of the repository. It omits generated files, caches, virtual environments, and individual data files that are not necessary for understanding the architecture.

```text
.
├── data/
│   ├── assessment/
│   ├── bgg_games/
│   ├── bgg_raw_htmls/
│   ├── game_ids/
│   ├── indexes/
│   ├── wiki/
│   ├── wiki_extracted/
│   ├── experiment_results/
│   ├── lucene_experiment_results/
│   └── ...
│
├── docs/
│   ├── consultation_3/
│   ├── diagrams/
│   └── PROJECT_ARCHITECTURE.md
│
├── experiments/
│   ├── dataanalysis/
│   └── retrieval/
│       ├── config.py
│       ├── ranking.py
│       ├── results.py
│       ├── run_experiments.py
│       ├── search_sqlite.py
│       ├── run_lucene_experiments.py
│       ├── search_lucene.py
│       └── ...
│
├── legacy/
│   ├── README.md
│   ├── baseline_indexers.py
│   └── ...
│
├── src/
│   ├── indexing/
│   │   ├── builder.py
│   │   ├── database.py
│   │   ├── query.py
│   │   ├── retrieval.py
│   │   └── tokenizer.py
│   │
│   ├── lucene/
│   │   ├── analyzer.py
│   │   ├── builder.py
│   │   └── search.py
│   │
│   ├── scripts/
│   │   └── extract_wikipedia_for_bgg.py
│   │
│   ├── wiki_extraction.py
│   ├── wiki_spark_extraction.py
│   └── ...
│
└── testing/
    ├── fixtures/
    ├── test_indexing.py
    ├── test_query.py
    ├── test_retrieval.py
    ├── test_ranking.py
    ├── test_spark_extraction_integration.py
    ├── test_wiki_extraction.py
    ├── test_wikipedia_game_fields.py
    └── test_search_cli.py
```

### Main directory responsibilities

| Directory | Responsibility |
|---|---|
| `src/` | Main application and data-processing implementations. |
| `src/indexing/` | SQLite index construction, access, query processing, and candidate retrieval. |
| `src/lucene/` | Lucene analysis, index construction, and search implementation. |
| `src/scripts/` | Executable scripts for specific data-processing tasks. |
| `experiments/` | Retrieval experiments, ranking configurations, comparison, and evaluation workflows. |
| `testing/` | Automated tests and test fixtures. |
| `data/` | Input datasets, intermediate processing data, indexes, assessments, and generated experiment files. |
| `docs/` | Project documentation, consultation material, and diagrams. |
| `legacy/` | Older implementations retained for reference; not the location of the current indexing architecture. |

The distinction between `src` and `experiments` is important: `src` contains reusable functionality, while `experiments` contains workflows that use that functionality to run searches, compare configurations, or evaluate retrieval approaches.

---

## 3. Overall component relationships

At a high level, the data and retrieval workflow is organised as follows:

```text
                         BGG source data
                                |
                +---------------+----------------+
                |                                |
                v                                v
        SQLite indexing                 Spark / Wikipedia
                |                                |
                v                                v
        SQLite index                  Wikipedia processing
                |                                |
                v                                v
        SQLite search                  Enriched BGG dataset
                |                                |
                v                                v
       TF-IDF experiments                 Lucene builder
                |                                |
                |                   +------------+------------+
                |                   |                         |
                |                   v                         v
                |              BGG-only index           Enriched index
                |                   |                         |
                |                   +------------+------------+
                |                                |
                |                                v
                |                          Lucene search
                |                                |
                |                                v
                |                       Lucene experiments
                |                                |
                +---------------+----------------+
                                |
                                v
                       Retrieval evaluation
                                |
                                v
                  TF-IDF baseline vs. Lucene
                    (BM25 retrieval approach)
                                |
                                v
                 Comparison of retrieval quality
                     (including precision)
```



The SQLite and Lucene components are two separate retrieval implementations. They share the same general BGG collection and aim to provide comparable search conditions, but they use different ranking approaches.

The Spark component is responsible for processing and enriching data. It does not provide the interactive search functionality itself. Its output can subsequently be used as input to the Lucene index builder.

---

# 4. SQLite indexing and retrieval

## 4.1 Component overview

The SQLite implementation is the project's baseline inverted-index system. Its responsibilities are divided into several modules under `src/indexing/`.

```text
src/indexing/
├── builder.py
├── database.py
├── query.py
├── retrieval.py
└── tokenizer.py
```

### `builder.py` – index construction

Responsible for creating the persistent SQLite index from the source BGG dataset.

Its main operation is `SQLiteIndexBuilder.build(source_path, database_path)`. It handles input validation, token processing, index population, metadata, and publication of the completed database.

This is a programmatic builder rather than a standalone command-line script.

### `database.py` – index access

Responsible for opening and accessing an existing SQLite index.

The `SQLiteIndex` class provides the interface used by query and retrieval operations to access documents, terms, postings, and index metadata.

It does not perform query ranking or build a new index.

### `tokenizer.py` – text tokenization

Contains the shared tokenization logic used by the SQLite implementation. It converts input text into normalized terms according to the project's tokenization rules.

### `query.py` – query processing

Responsible for converting a user's search text into the normalized query-term representation used by retrieval and ranking.

### `retrieval.py` – candidate retrieval

Responsible for finding documents that contain query terms and retrieving the document-term information required by the ranking stage.

Candidate retrieval is separate from the calculation of relevance scores.

## 4.2 SQLite ranking and experiment support

The ranking and experiment configuration code is located in `experiments/retrieval/`, rather than inside `src/indexing/`.

```text
experiments/retrieval/
├── config.py
├── ranking.py
├── results.py
└── run_experiments.py
```

- **`config.py`** defines the available TF, IDF, and normalization methods and represents a ranking configuration.
- **`ranking.py`** calculates term weights, document scores, and ranked search results for a selected configuration.
- **`results.py`** defines the result representation used by the retrieval experiments.
- **`run_experiments.py`** runs the configured TF-IDF experiments for a query and records their outputs.

This separation keeps the SQLite index implementation independent of the experiment configuration. The experiment ranking code uses the lower-level index and retrieval interfaces.

## 4.3 SQLite entry points

There are two different ways to use the existing SQLite index.

### Ordinary search

`experiments/retrieval/search_sqlite.py` is the general-purpose search entry point. It opens an existing index, processes the query, retrieves candidates, and ranks them using one selected TF-IDF configuration.

Run from the repository root:

```bash
python3 -m experiments.retrieval.search_sqlite "cooperative disease"
```

Display more or fewer results:

```bash
python3 -m experiments.retrieval.search_sqlite "cooperative disease" --top 5
```

Select a ranking configuration:

```bash
python3 -m experiments.retrieval.search_sqlite \
    "cooperative disease" \
    --tf logarithmic \
    --idf smoothed \
    --normalization euclidean \
    --top 10
```

The index path can be changed with `--database`.

### Run TF-IDF experiments

`experiments/retrieval/run_experiments.py` is the experiment runner. It evaluates the available TF-IDF configurations for the supplied query rather than selecting only one configuration.

```bash
python3 -m experiments.retrieval.run_experiments "cooperative disease" --top 5
```

The runner uses the existing SQLite index by default. It does not need to rebuild the index for each query.

**Use `search_sqlite.py` for an ordinary search demonstration and `run_experiments.py` when the purpose is to compare TF-IDF configurations.**

## 4.4 Building the SQLite index

The SQLite builder is exposed through the `SQLiteIndexBuilder` API in `src/indexing/builder.py`, not through a dedicated command-line interface.

A small Python invocation from the repository root can build an index:

```bash
python3 -c "from src.indexing.builder import SQLiteIndexBuilder; SQLiteIndexBuilder().build('data/bgg_games/bgg_games_deduplicated_20261121_003935.tsv', 'data/indexes/bgg_games.sqlite3')"
```

Use an appropriate source path and destination for the dataset being indexed. Building an index is a separate operation from searching it; the search entry points open an existing index and do not rebuild it.

---

# 5. Wikipedia extraction and Spark processing

## 5.1 Component overview

The Wikipedia component is responsible for extracting information from Wikipedia and associating it with BGG games.

Its implementation is split between two main modules:

```text
src/
├── wiki_extraction.py
├── wiki_spark_extraction.py
└── scripts/
    └── extract_wikipedia_for_bgg.py
```

### `wiki_extraction.py` – page parsing and extraction logic

Contains the lower-level Wikipedia processing functionality, including:

- parsing Wikipedia page records;
- extracting and resolving redirect targets;
- building title indexes;
- cleaning extracted values;
- extracting infobox parameters;
- extracting selected board-game attributes.

This module contains reusable parsing and extraction logic. It is not the Spark pipeline's command-line entry point.

### `wiki_spark_extraction.py` – distributed processing stages

Contains the Spark-based operations that process the BGG data and Wikipedia dump.

Its principal stages are:

1. **Candidate matching** – identify Wikipedia pages whose titles or title variants may correspond to BGG games.
2. **Redirect resolution** – resolve Wikipedia redirects so that candidate associations can refer to their destination pages.
3. **Attribute extraction** – extract selected fields from the relevant Wikipedia pages and associate them with candidate matches.
4. **Candidate ranking** – calculate heuristic scores and identify the best candidate for each BGG game.

The stages are implemented as separate functions so that their responsibilities can be inspected and used independently.

### `scripts/extract_wikipedia_for_bgg.py` – extraction entry point

This script starts a Spark session and runs the initial distributed extraction and candidate-matching stage.

It is the entry point for that initial stage, not a single command that automatically executes every later enrichment stage.

## 5.2 Data flow

The intended processing flow is:

```text
BGG source dataset                Wikipedia XML dump
        |                                  |
        +----------------+-----------------+
                         |
                         v
                Candidate extraction
                         |
                         v
                 Candidate matches
                         |
                         v
                 Redirect resolution
                         |
                         v
                 Attribute extraction
                         |
                         v
                 Candidate ranking
                         |
                         v
              Selected candidate data
                         |
                         v
               Integration with BGG
                         |
                         v
                Enriched BGG dataset
```

Intermediate processing outputs are stored under `data/wiki_extracted/`. Parquet is used for the intermediate datasets so that the results of individual processing stages can be stored and reused.

## 5.3 Running the initial Spark extraction

From the repository root:

```bash
python3 -m src.scripts.extract_wikipedia_for_bgg
```

This runs the initial extraction entry point using the paths and Spark settings defined in the script.

The remaining stages are implemented as separate functions in `src/wiki_spark_extraction.py`. The repository does not currently expose one verified command-line orchestrator that runs every stage through final BGG integration.

When working with existing intermediate outputs, inspect the corresponding stage and dataset before deciding whether it needs to be rerun. Reprocessing the complete Wikipedia dump is a separate and potentially expensive operation.

## 5.4 Important implementation boundary

The candidate-ranking function marks the best candidate but does not itself perform the complete final integration into a one-row-per-BGG-game dataset.

The final enriched Parquet dataset is present in the project and is used as the input to the Lucene builder. However, the source implementation that performs the final selected-candidate integration has not yet been identified as part of a single reproducible pipeline entry point.

This distinction is important when navigating the code:

- `wiki_extraction.py` contains page-level parsing and extraction logic.
- `wiki_spark_extraction.py` contains the distributed processing stages.
- `extract_wikipedia_for_bgg.py` starts the initial extraction stage.
- The final enriched dataset is a data asset consumed by later components.
- The existence of that dataset should not be mistaken for a complete, currently documented end-to-end orchestration command.

---

# 6. Lucene indexing and retrieval

## 6.1 Component overview

The Lucene implementation is located in `src/lucene/`.

```text
src/lucene/
├── analyzer.py
├── builder.py
└── search.py
```

### `analyzer.py` – text analysis

Defines the custom Lucene analyzer and its tokenization behavior.

The analyzer is designed to use the same tokenization pattern as the SQLite implementation. This helps keep text processing consistent when comparing the two retrieval systems.

### `builder.py` – index construction

Responsible for creating the two Lucene indexes:

- **BGG-only index** – uses the original BGG text fields.
- **Enriched index** – includes the BGG text fields and additional Wikipedia-derived fields.

The builder reads the enriched Parquet dataset and constructs both indexes. The original BGG text is represented separately through the `bgg_all_text` field so that searches over the original BGG content can be compared between the two indexes.

The builder validates the generated indexes and publishes them from temporary output directories. It refuses to overwrite existing destination indexes.

### `search.py` – search implementation

Contains the reusable `LuceneSearcher` class.

It provides methods for:

- general text search with Boolean AND or OR;
- phrase search;
- fuzzy search;
- numeric range search.

This module implements the search operations. The command-line interface described below is a separate wrapper around it.

## 6.2 Building Lucene indexes

The builder can be run as a Python module.

Display its available options:

```bash
python3 -m src.lucene.builder --help
```

The default source is the enriched Parquet dataset, and the default output root is `data/indexes`.

To build into a separate output root rather than overwrite or conflict with existing indexes:

```bash
python3 -m src.lucene.builder \
    --source data/wiki_extracted/bgg_wikipedia_enriched \
    --index-root data/indexes/lucene_rebuilt
```

The builder creates the BGG-only and enriched index directories under the specified root. Check the destination before running the command because index construction can take time and existing targets are not overwritten.

## 6.3 Ordinary Lucene search

`experiments/retrieval/search_lucene.py` provides the command-line interface for searching an existing Lucene index.

The default index root is:

```text
data/indexes/lucene_aligned/
```

The two index choices are `bgg_only` and `enriched`.

### General text search

```bash
python3 -m experiments.retrieval.search_lucene \
    "settlers catan" \
    --index bgg_only \
    --mode text \
    --operator OR \
    --limit 5
```

The text-search default field is `bgg_all_text`. The Boolean operator can be set to `AND` or `OR`.

### Phrase search

```bash
python3 -m experiments.retrieval.search_lucene \
    "settlers of catan" \
    --index enriched \
    --mode phrase \
    --limit 5
```

Phrase search defaults to the `game_title` field.

### Fuzzy search

```bash
python3 -m experiments.retrieval.search_lucene \
    catna \
    --mode fuzzy \
    --max-edits 2 \
    --limit 5
```

Fuzzy search defaults to `game_title`. The maximum edit distance can be selected with `--max-edits`.

### Numeric range search

```bash
python3 -m experiments.retrieval.search_lucene \
    --mode range \
    --field release_year \
    --lower 1990 \
    --upper 2000 \
    --limit 5
```

Range mode does not require a positional query. It requires both numeric bounds.

The index root can be changed with `--index-root`.

## 6.4 Lucene experiment entry point

`experiments/retrieval/run_lucene_experiments.py` is the formal Lucene experiment runner. It executes the predefined query set against one of the aligned indexes and records the experiment output.

Run it against the BGG-only index:

```bash
python3 -m experiments.retrieval.run_lucene_experiments --index bgg_only
```

Run it against the enriched index:

```bash
python3 -m experiments.retrieval.run_lucene_experiments --index enriched
```

This experiment runner is separate from `search_lucene.py`:

- `search_lucene.py` is intended for individual searches and query-type demonstrations.
- `run_lucene_experiments.py` runs the predefined experiment workflow and records its outputs.

---

# 7. Retrieval comparison and relevance evaluation

The retrieval evaluation workflows are located in `experiments/retrieval/`.

They support comparisons between the SQLite TF-IDF baseline and Lucene BM25 retrieval.

The main responsibilities are:

| Module | Responsibility |
|---|---|
| `compare_tfidf_lucene.py` | Compare the retrieval outputs of the TF-IDF and Lucene systems under the configured evaluation workflow. |
| `build_lucene_assessment_extension.py` | Extend the relevance-assessment pool with documents returned by Lucene. |
| `assess_relevance.py` | Manage relevance-assessment input and completed assessment files. |
| `evaluate_q01_relevance.py` | Evaluate the completed relevance assessments for the Q01 query. |
| `run_experiments.py` | Run the SQLite TF-IDF configuration experiments. |
| `run_lucene_experiments.py` | Run the predefined Lucene experiments. |

The assessment data is stored under `data/assessment/`, with separate locations for formal evaluation inputs and completed assessments.

The comparison workflow is distinct from ordinary searching. Its purpose is to evaluate retrieval systems under shared queries, assessment data, and evaluation procedures.

For the consultation, use the individual search CLIs to demonstrate how each retrieval system works. Use the experiment and evaluation scripts when demonstrating the formal comparison process.

---

# 8. Testing

Automated tests are located in `testing/`.

The tests cover the main areas of the project, including:

- SQLite index construction and access;
- query processing;
- candidate retrieval;
- ranking and ranking configurations;
- Wikipedia parsing and field extraction;
- Spark extraction integration;
- title matching;
- the SQLite and Lucene search command-line interfaces.

Test fixtures, including sample BGG HTML pages, are stored in:

```text
testing/fixtures/
```

Run the complete test suite from the repository root:

```bash
python3 -m pytest -q
```

Run tests for a particular component:

```bash
python3 -m pytest testing/test_indexing.py -q
```

Run the search CLI tests:

```bash
python3 -m pytest testing/test_search_cli.py -q
```

The search CLI tests mock the underlying index/searcher interfaces. They test the entry-point behavior without requiring the complete data indexes to be rebuilt.

---

# 9. Data and generated files

The `data/` directory contains both input data and generated artifacts. It is not part of the Python source architecture.

The main subdirectories are:

| Directory | Purpose |
|---|---|
| `data/bgg_games/` | Processed BGG game datasets used by indexing and enrichment. |
| `data/bgg_raw_htmls/` | Raw BGG HTML pages collected during data acquisition. |
| `data/game_ids/` | Game identifier data used by the collection and extraction workflows. |
| `data/wiki/` | Wikipedia source dump data. |
| `data/wiki_extracted/` | Intermediate and enriched Wikipedia processing outputs. |
| `data/indexes/` | Persistent SQLite and Lucene indexes. |
| `data/assessment/` | Relevance-assessment inputs and completed assessments. |
| `data/experiment_results/` | Outputs from SQLite retrieval experiments. |
| `data/lucene_experiment_results/` | Outputs from Lucene retrieval experiments. |

The generated data directories may contain multiple versions or intermediate outputs. Their presence does not necessarily mean that each directory is a current source-code entry point. The relevant builder or processing function should be consulted to determine how a particular artifact is produced.

---

# 10. Legacy code

The `legacy/` directory contains older implementations retained for historical reference.

In particular:

```text
legacy/baseline_indexers.py
```

contains an older baseline indexing implementation that was superseded by the modular SQLite implementation under:

```text
src/indexing/
```

New development and demonstrations should use the current implementation. The legacy files are retained for comparison and historical context rather than as the main application entry points.

---

# 11. Quick reference: which file should I use?

| Task | Main file or entry point |
|---|---|
| Build the SQLite index | `src/indexing/builder.py` (`SQLiteIndexBuilder`) |
| Open and inspect the SQLite index | `src/indexing/database.py` (`SQLiteIndex`) |
| Process a SQLite query | `src/indexing/query.py` |
| Retrieve SQLite candidates | `src/indexing/retrieval.py` |
| Search the existing SQLite index | `experiments/retrieval/search_sqlite.py` |
| Run TF-IDF experiments | `experiments/retrieval/run_experiments.py` |
| Parse Wikipedia pages | `src/wiki_extraction.py` |
| Run the initial Spark extraction stage | `src/scripts/extract_wikipedia_for_bgg.py` |
| Use Spark processing stages | `src/wiki_spark_extraction.py` |
| Configure Lucene text analysis | `src/lucene/analyzer.py` |
| Build Lucene indexes | `src/lucene/builder.py` |
| Use Lucene search operations | `src/lucene/search.py` |
| Search an existing Lucene index | `experiments/retrieval/search_lucene.py` |
| Run Lucene experiments | `experiments/retrieval/run_lucene_experiments.py` |
| Compare TF-IDF and Lucene | `experiments/retrieval/compare_tfidf_lucene.py` |
| Manage relevance assessments | `experiments/retrieval/assess_relevance.py` |
| Run automated tests | `python3 -m pytest -q` |

---

## 12. Suggested demonstration sequence

For a concise demonstration of the implemented components, the following order follows the project's architecture:

1. **SQLite baseline:** show the existing index and run `search_sqlite.py` with a query.
2. **TF-IDF experiments:** run `run_experiments.py` to show how the same index can be searched with different ranking configurations.
3. **Wikipedia processing:** explain the responsibilities of `wiki_extraction.py` and `wiki_spark_extraction.py`, then show the initial extraction entry point and the relationship between the intermediate processing stages.
4. **Lucene construction:** show `src/lucene/builder.py --help` and explain how it creates the BGG-only and enriched indexes from the enriched dataset.
5. **Lucene search:** demonstrate Boolean, phrase, fuzzy, and numeric range queries through `search_lucene.py`.
6. **Lucene experiments:** show `run_lucene_experiments.py` and explain how it differs from an individual search.
7. **Evaluation:** introduce the relevance-assessment and comparison scripts to explain how the two retrieval approaches are evaluated.

This sequence moves from the baseline index, through data enrichment, to the second retrieval implementation and its evaluation.

The individual components can also be demonstrated independently because their responsibilities and entry points are separated.
