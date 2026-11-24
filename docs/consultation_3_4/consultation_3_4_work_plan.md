# VINF — Consultation 3 and 4 Work Plan

Last updated: 2026-11-20
Status reflects the latest verified project information available in the development notes. Re-run the relevant checks before treating time-sensitive Git or environment states as current.

## Status legend

- [x] Completed and verified
- [ ] Not completed
- [~] Partially completed, or completed only in a limited/smoke-test sense

> These are standard Markdown task-list checkboxes. GitHub and many Markdown viewers render them as checked/unchecked boxes. Whether they can be toggled directly in the viewer depends on the platform; the portable way to update them is to edit `[ ]` to `[x]` (or vice versa) in the Markdown file.

---

# Phase 1 — Repository audit

**Goal:** Establish a known, clean and reproducible Git baseline before further implementation.

- [x] Inspect the repository structure and identify the main source, data, documentation and experiment areas.
- [x] Inspect `git status` and remove the temporary diagnostic script / revert unintended `.gitignore` changes.
- [x] Compare local `main` with `origin/main`.
- [x] Verify that important project files are tracked and intended new files are included.
- [x] Inspect `.gitignore` for datasets, raw HTML, TSV/CSV/JSON exports, compressed dumps, generated indexes, Spark output and virtual environments.
- [x] Review staged changes, confirm both Python file relocations and check for whitespace errors.
- [x] Commit the final repository baseline and documentation.
- [x] Push to GitHub and verify that local `main` and `origin/main` point to the same commit.

### Verified Git state

#### Latest verified Git state

- Branch: `main`.
- Working tree: clean.
- Local `main` and `origin/main` point to the same commit.
- Latest commit: `33fd1d37f024c0e8db5f4849189ba971b177b8c3`.
- Commit message: `chore(repo): finalize project baseline and documentation`.
- All intended documentation and experiment-file changes have been committed and pushed.

#### Audit on 2026-11-20:

- Current branch was `main`.
- Working tree was clean (`git status --short --branch` returned `## main`).
- Local `main` was one commit ahead of `origin/main` (`0 1` from `git rev-list --left-right --count origin/main...HEAD`).
- There were no remote-only commits at that time.
- The local-only commit was `a5cd6c6` — `chore(repo): clean ignored browser profile and organize legacy/experiments`.
- `origin/main` was at `25c261f` — `feat(crawler): add resumable BGG crawling with periodic checkpoints`.
- No push had been performed as part of that audit.

**Conclusion:** The repository audit and cleanup are complete. The final documentation and experiment-file reorganisation have been staged and reviewed. Phase 1 remains in progress until the final commit is pushed and the remote repository is verified.

---

# Phase 2 — Environment verification

**Goal:** Verify that the Python, Spark and Lucene toolchain can actually execute, not merely that packages appear installed.

- [x] Python 3.11.18 environment created and verified in WSL.
- [x] OpenJDK 17 installed and verified, including the JNI/JVM development files needed for the native bridge.
- [x] Apache Ant 1.10.15 installed and verified.
- [x] PySpark 4.3.0 installed.
- [x] Start a local PySpark session (`local[2]`) and run a DataFrame smoke test successfully.
- [x] Build and install PyLucene 9.12.0.
- [x] Initialize the JVM through PyLucene, create an in-memory Lucene index, index a document and successfully retrieve it with a search query.
- [x] Verify JCC installation and native extension import.

### JCC version clarification

The verified setup uses **JCC 3.14**, not JCC 3.15. This is intentional: the project built **PyLucene 9.12.0** from its source distribution, which bundles the matching JCC 3.14 source. The successful build used JCC's non-shared mode. Do not upgrade to JCC 3.15 merely to match an earlier checklist: JCC must match the selected PyLucene release and its build requirements. If the PyLucene version is changed later, reassess the Java/JCC/Python compatibility as a set.

### Verification details

- PySpark smoke test: Spark 4.3.0 started; `spark.range(5)` displayed rows 0–4 and returned count 5.
- PyLucene smoke test: PyLucene 9.12.0 initialized the JVM, indexed the sentence `Catan is a popular strategy board game.`, searched for `strategy` and returned one matching document.
- These are runtime smoke tests. They do not prove that the project's full Wikipedia/Spark pipeline or production BGG Lucene index is implemented.

**Conclusion:** Phase 2 is **complete for the selected compatible stack**. The only apparent discrepancy is the earlier JCC 3.15 item, which should be corrected to JCC 3.14 for the currently verified PyLucene 9.12.0 setup.

---

# Phase 3 — Dataset inspection and preparation

**Goal:** Understand the BGG and Wikipedia inputs and define a defensible extraction and matching strategy before building the Spark pipeline.

- [~] Inspect the BGG TSV structure. The project has a 42-field TSV and the indexer’s selected text fields have been inspected; the final dataset schema, row count and data-quality profile still need to be recorded from the exact input file used for the consultation.
- [x] Inspect the existing custom TF-IDF implementation in `src/indexers.py` at source-code level.
- [ ] Produce a field inventory for all 42 BGG fields, including type/meaning, missing-value frequency and whether each field is useful for indexing, joining or display.
- [ ] Inspect the Wikipedia `.xml.bz2` dump structure and confirm the exact dump version/source.
- [ ] Identify candidate Wikipedia attributes to extract and retain.
- [ ] Define and document the BGG-to-Wikipedia matching strategy, including normalization, candidate keys, ambiguity handling and false-match checks.
- [ ] Establish baseline dataset statistics: number of BGG records, unique identifiers, missing/duplicate IDs and relevant text-field coverage.

---

# Phase 4 — Implementation and evaluation

**Goal:** Complete the consultation 3 Spark enrichment workflow and consultation 4 PyLucene search workflow, then evaluate them against the custom indexer.

## 4.1 Retrieval-weighting analysis before implementation changes

- [x] Review the lecture material on TF, IDF, normalization, vector-space retrieval and BM25.
- [x] Record the existing custom indexer's two IDF methods: classic IDF and smoothed IDF.
- [ ] Work through a small numerical example using the same hypothetical board-game documents for the five lecture TF schemes and three lecture IDF schemes.
- [ ] Compare term weights and document scores, and observe how the rankings change across at least three representative queries.
- [ ] Decide which lecture-taught TF/IDF/normalization variants are worth implementing in the custom indexer.
- [ ] Preserve the existing implementation as the baseline and explain the rationale for each selected method.
- [ ] Keep BM25 out of the custom-indexer comparison for now; use Lucene's BM25 as the advanced ranking comparison unless the assignment or lecturer gives a different direction.

## 4.2 Consultation 3 — Spark and Wikipedia processing

- [ ] Implement Wikipedia dump extraction using the required regex-based approach.
- [ ] Implement Spark transformations for the extracted records.
- [ ] Apply the documented BGG/Wikipedia matching strategy and join the datasets.
- [ ] Validate the join: inspect unmatched records, duplicate matches and suspicious/ambiguous matches.
- [ ] Export the enriched dataset in a documented format and location.
- [ ] Report the number of unique Wikipedia pages joined to BGG records.
- [ ] Identify and report the useful Wikipedia attributes retained in the enriched dataset.
- [ ] Record execution details and relevant statistics so the consultation can be reproduced.

## 4.3 Custom Python indexer and IDF requirement

- [x] Implement a custom inverted index with term-frequency storage.
- [x] Implement at least two IDF-based ranking methods: classic IDF and smoothed IDF.
- [ ] Document the index structure, what is indexed, how often the index is built, and whether the build is full/static or incremental.
- [ ] Demonstrate the behaviour of the IDF methods on at least three queries using the same collection and comparable settings.
- [ ] Implement any additional lecture-based weighting variants selected in section 4.1.
- [ ] Separate reusable indexer classes from command-line argument parsing; `indexers.py` currently creates its argument parser at module level, which can cause import-time side effects.
- [ ] Ensure the custom indexer can be imported and reused by evaluation scripts without unexpectedly parsing command-line arguments.

## 4.4 Consultation 4 — PyLucene schema and search

- [x] Verify that PyLucene can initialize and perform an in-memory index/search operation.
- [ ] Design the project Lucene schema for BGG and enriched Wikipedia data.
- [ ] Decide which fields are analyzed text, exact-match fields, stored display fields, filterable fields or numeric fields.
- [ ] Implement construction of the persistent/project Lucene index from the prepared dataset.
- [ ] Implement and test Boolean queries.
- [ ] Implement and test range queries.
- [ ] Implement and test phrase queries.
- [ ] Implement and test fuzzy queries.
- [ ] Configure and document the Lucene analyzer and BM25 parameters used for ranked retrieval.
- [ ] Add repeatable query examples and tests for the required query types.

## 4.5 Comparison and reporting

- [ ] Compare the custom Python indexer with Lucene using the same dataset and a stable query set.
- [ ] Keep query preprocessing and field choices as consistent as reasonably possible; document unavoidable differences.
- [ ] Prepare relevance judgments or another defensible basis for assessing result quality.
- [ ] Compare ranked examples and, where relevance judgments support it, metrics such as Precision@k, Recall@k, MAP or NDCG.
- [ ] Explain observed differences rather than assuming the more complex engine must perform better.
- [ ] Later, complete the required comparison with Google and the original crawled domain.
- [ ] Document limitations, implementation decisions and reproducibility instructions for the consultations and final presentation.

---

# Immediate next actions

1. [ ] Commit the reviewed README, documentation and experiment-file reorganisation.
2. [ ] Push the local commits to GitHub and verify that `main` and `origin/main` are synchronized.
3. [ ] Carry out the numerical TF/IDF experiment before changing the custom indexer.
4. [ ] Return to Phase 3 dataset inspection and then implement the Consultation 3 Spark workflow.

## Important scope and decision notes

- A successful environment smoke test is not the same as a completed project pipeline.
- Keep the existing custom TF-IDF implementation as a transparent baseline.
- Treat TF weighting, IDF weighting and document-length normalization as separate design choices during experiments.
- The current custom indexer uses raw/natural TF with classic or smoothed IDF and no document-length normalization; confirm the exact implementation again before changing it.
- The lecture-taught probabilistic IDF is not synonymous with BM25. BM25 is a separate ranking function that combines term-frequency saturation, IDF and document-length normalization.
- The lecture's clipped probabilistic IDF can assign zero weight to a common query term. That term then contributes zero, but the total document score can still be positive because other query terms may contribute nonzero scores.
- Do not introduce several changes at once in an experiment. Otherwise, it becomes difficult to attribute ranking differences to a particular method.
