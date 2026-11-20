# Project status and implementation roadmap

Last documented: 2026-11-20

This document records the work completed so far, the current technical state, and the intended remaining work. Status labels describe what has been verified in the development environment; they do not imply that every course deliverable has already been completed.

## 1. Project objective

Build and evaluate a search engine over BoardGameGeek board-game records. The project combines:

1. a custom Python inverted index and ranking baseline;
2. Spark-based processing and enrichment using a Wikipedia dump;
3. a Lucene/PyLucene search implementation;
4. retrieval-model and query-feature comparisons;
5. evaluation and reporting suitable for the VINF consultations and final presentation.

The dataset has been described during development as approximately 17,652 BGG game records, with a TSV containing 42 fields. The exact record count should be rechecked against the final dataset before reporting it as a final result.

## 2. Work completed

### 2.1 BGG collection and dataset preparation — implemented

The repository already contains a BGG crawling and extraction workflow. Recent Git history includes work on HTML crawling, game metadata extraction, relationship parsing, TSV writing and validation, reparsing existing records, resumable graph crawling and periodic checkpoints.

The project uses a tab-separated BGG dataset. Large raw data and generated files are excluded from version control through `.gitignore` rules.

The exact completeness and quality of the final dataset still need to be checked before the final evaluation.

### 2.2 Custom Python indexer — implemented baseline

`src/indexers.py` contains `BGGIndexer`, which:

- reads BGG records from a TSV file using `csv.DictReader`;
- skips rows without an `app_id`;
- combines selected textual fields, including title, alternate names, descriptions, game type, categories, mechanics, family, designer, publisher and awards;
- tokenizes text using a regular expression;
- builds an in-memory inverted index mapping terms to document IDs;
- stores per-document term frequencies;
- calculates classic and smoothed IDF;
- ranks documents by summing term-frequency × IDF contributions.

The current tokenizer is based on `re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())`. Consequently, it is limited to ASCII alphabetic tokens of at least three characters. This is a known baseline limitation, not a claim that the tokenizer is ideal for all BGG text.

The current indexer is a useful transparent baseline, but it does not currently implement document-length normalization, field-specific weighting, phrase matching or a BM25 ranking function.

### 2.3 Lecture review — completed for the relevant weighting material

The lecture presentation `06_seleng_ir_indexovanie.pdf` was examined, including slides 44–49 and the surrounding material:

- slide 44: logarithmic TF motivation and formula;
- slide 45: maximum-TF normalization;
- slide 46: document length and Euclidean normalization;
- slide 47: summary of five TF variants;
- slide 48: natural, standard and probabilistic IDF;
- slide 49: no normalization, Euclidean/cosine normalization and byte-length normalization associated with Okapi BM25;
- slides 50–51: worked TF-IDF scoring example;
- slides 52–61: vector-space model and cosine similarity;
- slide 63: Okapi BM25 and the negative-IDF issue.

The detailed notes are in [`lecture_06_retrieval_weighting.md`](lecture_06_retrieval_weighting.md).

### 2.4 PySpark environment — installed and smoke-tested

Verified environment:

- PySpark 4.3.0
- Python 3.11.18
- Java 17

A local Spark session using `local[2]` was started successfully. A small `spark.range(5)` DataFrame was displayed and counted successfully. This verifies that the local PySpark runtime works; it does **not** mean that the Wikipedia extraction and join pipeline has been implemented or validated.

### 2.5 PyLucene environment — built, installed and smoke-tested

Verified environment:

- PyLucene 9.12.0
- JCC 3.14
- OpenJDK 17
- Apache Ant 1.10.15
- Python 3.11.18

PyLucene 9.12.0 was built from the official source archive, using the JCC version bundled with the source distribution. The JCC extension was built in non-shared mode because the installed JCC configuration did not support the requested shared mode. The resulting Lucene Python wheel was installed successfully.

A smoke test initialized the JVM, created an in-memory Lucene index, indexed a short board-game sentence, searched for `strategy`, and returned one matching document. This verifies the basic PyLucene/JVM bridge and indexing/search path; it does **not** mean the project's BGG index schema or required query features are complete.

### 2.6 Git repository housekeeping — verified clean at last check

#### 1st Audit (19th Nov. 2026)

At the repository audit:

- branch: `main`;
- local `main` was one commit ahead of `origin/main`;
- there were no remote-only commits;
- a temporary diagnostic script was removed;
- `.gitignore` was restored;
- `git status --short --branch` returned only `## main`.

No push was performed as part of that audit. Recheck Git status and remote divergence before the next commit or push because repository state may have changed since this note was written.

#### 2nd Audit (20th Nov. 2026)

the intended changes are staged, both relocations are 100% identical, and the staged whitespace check is clean. State explicitly that the final commit and push are still pending.

## 3. Course requirements and remaining work

The following is the working plan based on the consultations and requirements discussed so far. Confirm the exact wording against the official assignment document before final submission.

| Work package | Intended output | Current state |
|---|---|---|
| BGG crawling and TSV preparation | A reproducible BGG dataset with validated records | Implemented; final dataset validation/count still required |
| Custom indexer and index description | Explain index structure, TF, indexing frequency/build process | Basic custom indexer implemented; documentation and final explanation remain |
| At least two IDF ranking methods | Implement and explain at least two IDF variants | Classic and smoothed IDF already implemented; lecture-based comparison/selection remains |
| Compare IDF methods on at least three queries | Demonstrate ranking differences on a fixed query set | Not yet documented as a controlled experiment |
| Spark/Wikipedia processing | Extract relevant Wikipedia pages using regex, process in Spark and join with BGG | Environment verified; pipeline still to implement/validate |
| Join report | Report number of unique Wikipedia pages joined and useful enriched attributes | Pending Spark pipeline |
| PyLucene schema and index | Define fields and integrate BGG/Wikipedia data | PyLucene runtime verified; project schema/integration pending |
| Lucene query types | Boolean, range, phrase and fuzzy queries | Pending project implementation and tests |
| Compare custom index and Lucene | Compare retrieval behaviour using controlled queries | Pending |
| External search comparison | Compare results with Google and the original crawled domain | Later project phase; pending |
| Final documentation and presentation | Explain decisions, methods, evaluation and reproducibility | In progress; these documents establish the foundation |

## 4. Planned next phases

### Phase A — documentation and reproducibility

- Maintain this status/roadmap document.
- Document the lecture's TF, IDF and normalization methods.
- Document the verified Python, Spark and PyLucene environment.
- Explain how to reproduce the environment and smoke tests.
- Clarify which dependency file/tool is authoritative for the project.

### Phase B — controlled analysis of lecture weighting methods

Before changing the indexer, calculate and compare the five lecture TF schemes and three IDF schemes on a small, shared hypothetical collection. Use the exercise to understand how the methods change individual term weights and final rankings.

Then select a limited number of methods for implementation. Preserve the existing classic and smoothed IDF methods as the baseline comparison. Probabilistic IDF can be evaluated as a lecture-taught alternative, but its zero-floor behaviour must be explained. Do not add BM25 to the custom baseline merely to duplicate Lucene's planned BM25 comparison.

### Phase C — improve and test the custom indexer

- Separate reusable indexer classes from command-line argument parsing. The parser is currently created at module level, which can cause import-time side effects.
- Add selected weighting schemes behind explicit, documented options.
- Add document-length normalization only as a separately controlled component.
- Ensure all variants use the same tokenizer, fields, dataset and query set when compared.
- Record the number of index builds and whether the index is rebuilt from the full collection or updated incrementally. The current in-memory implementation builds from the TSV when invoked; it is not a persistent incremental index.

### Phase D — Spark and Wikipedia enrichment

- Inspect the dump format and determine the extraction strategy.
- Use Spark for distributed processing as required by the consultation.
- Extract candidate Wikipedia page titles/content with the specified regex-based approach.
- Join the extracted pages with BGG records using a documented matching key/normalization strategy.
- Report unique pages joined and the useful attributes retained.
- Validate join coverage and inspect false matches/missing matches.

### Phase E — PyLucene integration

- Define a field schema appropriate for BGG and enriched Wikipedia data.
- Decide which fields are searchable, stored, exact-match/filterable or numeric.
- Implement and test Boolean, range, phrase and fuzzy queries.
- Use BM25 as a Lucene ranking baseline, documenting its parameters and analyzer configuration.
- Compare it with the custom Python ranking models, keeping tokenization and query conditions as consistent as reasonably possible.

### Phase F — evaluation and final comparison

- Prepare at least three representative queries for the IDF comparison requirement; preferably use a larger stable query set for broader evaluation.
- Define relevance judgments before comparing ranking methods.
- Report both ranked examples and suitable metrics such as Precision@k, Recall@k, MAP or NDCG where the relevance data supports them.
- Later compare with Google and the original crawled domain as required by the course.
- Document limitations and explain why the chosen method is appropriate for this dataset and task.

## 5. Important implementation decisions to preserve

- Keep the existing custom indexer as a transparent baseline rather than replacing it prematurely.
- Keep TF weighting, IDF weighting and document-length normalization conceptually separate and configurable.
- Do not attribute ranking improvements to a single change if several components were changed simultaneously.
- Do not claim that a local Spark or PyLucene smoke test proves that the course pipeline is complete.
- Do not compare two implementations of the same ranking model unless implementation equivalence is itself the research question.
