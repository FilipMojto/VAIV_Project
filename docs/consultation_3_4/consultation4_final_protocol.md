# Consultation 4 – PyLucene Indexing and Retrieval Evaluation

## 1. Objective

The objective of this consultation was to implement a persistent search index using PyLucene, integrate it into the board-game retrieval application, and compare its retrieval behaviour with the previously developed TF-IDF search system.

The implementation builds on the enriched BoardGameGeek (BGG) dataset produced during Consultation 3. This dataset contains the original BGG records together with selected information extracted from matching Wikipedia articles.

The work covers three main areas:

1. Design and implementation of two persistent Lucene indexes.
2. Implementation of text, phrase, fuzzy and numeric range queries.
3. Comparison of Lucene BM25 rankings with the existing TF-IDF configurations, supplemented by a relevance-based evaluation.

## 2. PyLucene index design and implementation

### 2.1 Index architecture

The implementation is located in `src/lucene/` and is divided into separate modules:

| Module | Responsibility |
|---|---|
| `analyzer.py` | Defines text tokenization and normalization |
| `builder.py` | Builds and validates persistent Lucene indexes |
| `search.py` | Implements index access and retrieval operations |
| `__init__.py` | Package initialization |

The builder creates two indexes from the same enriched BGG dataset:

- **BGG-only index (`lucene_bgg`)** – contains the original BGG attributes.
- **Enriched index (`lucene_enriched`)** – contains the BGG attributes and additional Wikipedia-derived information.

Both indexes contain the same BGG documents, identified by their `app_id`. This allows the retrieval systems to be compared using the same underlying collection.

The indexes are persistent and stored under `data/indexes/`. The builder streams records from the Spark dataset using `toLocalIterator()` rather than collecting the entire dataset into memory. It also validates the input schema, checks for duplicate identifiers, builds temporary index directories, commits the indexes, and verifies their document counts before publishing them.

The final enriched dataset used for the latest build is:

`data/wiki_extracted/bgg_wikipedia_enriched_v3`

The resulting indexes contain 17,648 BGG game records each.

### 2.2 Field design and justification

The index uses different Lucene field types depending on how each attribute is expected to be searched or retrieved.

| Field type | Purpose |
|---|---|
| `TextField` | Tokenized and searchable text |
| `StringField` | Exact-value searchable fields |
| `IntPoint` | Numeric range searching |
| `StoredField` | Retains values for retrieval without making them searchable |

This distinction avoids indexing every attribute unnecessarily while ensuring that useful metadata remains available in search results.

#### BGG text fields

The following BGG attributes are indexed as text:

- `game_title`
- `alternate_names`
- `short_description`
- `description`
- `game_type`
- `game_category`
- `game_mechanic`
- `game_family`
- `designer`
- `publisher`
- `awards_honors`

These fields represent the main descriptive and categorical information about each board game. They support searches based on game names, themes, mechanics, designers, publishers and other descriptive characteristics.

The game title is also stored so that it can be displayed in search results. The other individual BGG text fields are indexed but are not stored individually.

A combined field, `bgg_all_text`, is created by concatenating the BGG text attributes. It provides a common search field for general queries and allows consistent comparison between the BGG-only and enriched indexes.

Importantly, `bgg_all_text` contains BGG text attributes only. Wikipedia information is indexed separately rather than being added to this combined field.

#### BGG numeric fields

The following attributes are indexed numerically:

- `release_year`
- `num_of_players_min`
- `num_of_players_max`
- `play_time_min`
- `play_time_max`

They are implemented using `IntPoint`, which supports numeric range queries. Corresponding `StoredField` values retain the original numbers so they can also be displayed in the results.

These attributes are useful for filtering games by publication year, supported player counts and playing time.

#### Wikipedia-derived fields

The enriched index additionally contains the following searchable text fields:

- `wiki_short_description`
- `wiki_designer`
- `wiki_publisher`
- `wiki_number_of_players`
- `wiki_playing_time`
- `wiki_publication_history`
- `wiki_setup_time`
- `wiki_chance`

These attributes provide complementary information that may be absent or incomplete in the original BGG record. They are indexed as `TextField` values and stored so that their contents can also be displayed.

The `wiki_infobox_type` attribute is indexed as a `StringField`, because it represents a categorical value that is more appropriately matched exactly than tokenized as ordinary text.

Other Wikipedia-related attributes are retained as stored metadata:

- `wiki_matched_page_id`
- `wiki_matched_title`
- `wiki_page_id`
- `wiki_title`
- `wiki_release_date`
- `wiki_official_website`
- `wiki_matched_variant_type`
- `wiki_redirect_status`
- `wiki_candidate_score`

These fields provide information about the selected Wikipedia match, its identity, the matching process and additional extracted metadata. They are available in retrieved documents but are not used as searchable fields in the current implementation.

Finally, `app_id` is indexed as a stored `StringField`. This supports exact document identification and allows the original BGG identifier to be returned with each result.

### 2.3 Text analysis

The shared analyzer is implemented in `src/lucene/analyzer.py`.

It uses a `PatternTokenizer` with the regular expression:

`\b[a-zA-Z]{3,}\b`

The resulting tokens are converted to lowercase using a lowercase filter.

Consequently:

- Only alphabetic tokens are retained.
- Tokens must contain at least three characters.
- Uppercase and lowercase forms are normalized.
- No stemming or stop-word removal is performed.

The same tokenization approach is used in the existing SQLite-based retrieval implementation. This helps maintain consistency when comparing the behaviour of the different retrieval systems.

### 2.4 Ranking model

Lucene uses BM25 similarity with the following parameters:

- \(k_1 = 1.2\)
- \(b = 0.75\)

BM25 ranks documents according to the relevance of their matching terms, taking term frequency, inverse document frequency and document length into account.

These parameters are explicitly configured in the search implementation rather than relying on an unspecified default.

## 3. Search functionality

The retrieval implementation is provided by `src/lucene/search.py` and exposed through the command-line interface in `experiments/retrieval/search_lucene.py`.

Four query modes are supported.

### 3.1 Boolean text queries

Ordinary text queries are parsed using Lucene's `QueryParser`.

Two Boolean operators are supported:

- **OR** – a document may match any of the query terms.
- **AND** – a document must match all query terms.

OR is the default operator. The search field can also be specified, allowing queries to target individual indexed attributes instead of the combined BGG text field.

### 3.2 Phrase queries

Phrase queries search for terms occurring together in the specified order.

The implementation uses a quoted phrase with Lucene's query parser. This is useful when the relationship and order of words matter, rather than merely finding documents containing the individual terms.

### 3.3 Fuzzy queries

Fuzzy queries support approximate matching of a search term, allowing a limited number of character edits.

The maximum edit distance can be configured as:

- 0 edits – exact term matching.
- 1 edit – one character insertion, deletion or substitution.
- 2 edits – up to two edits.

The default is two edits. The current implementation normalizes the input using the analyzer and uses its first token for the fuzzy query. Therefore, fuzzy search is a single-term operation even when the input contains multiple words.

### 3.4 Numeric range queries

Range queries filter documents according to numeric attributes.

The currently supported fields are the five BGG numeric attributes:

- `release_year`
- `num_of_players_min`
- `num_of_players_max`
- `play_time_min`
- `play_time_max`

The implementation uses `IntPoint.newRangeQuery()` and applies inclusive lower and upper bounds.

This makes it possible to retrieve games whose numeric attributes fall within a specified interval.

## 4. Application integration

The Lucene search functionality is exposed through:

`experiments/retrieval/search_lucene.py`

The command-line application allows the user to select:

- The BGG-only or enriched index.
- The query mode.
- The search field.
- The Boolean operator for text queries.
- The maximum edit distance for fuzzy queries.
- The numeric range bounds.
- The maximum number of returned results.

The default index root is `data/indexes/lucene_updated`.

The two index choices are:

| CLI selection | Index |
|---|---|
| `bgg_only` | `lucene_bgg` |
| `enriched` | `lucene_enriched` |

The default text-search field is `bgg_all_text`. Phrase and fuzzy queries default to `game_title`, while numeric range queries default to `release_year`.

For the enriched index, the search application can also display the stored Wikipedia-derived metadata alongside the original BGG information.

An important distinction is that selecting the enriched index does not automatically incorporate Wikipedia text into a general `bgg_all_text` query. Wikipedia text fields can instead be targeted explicitly using the field-selection option.

## 5. Retrieval evaluation: TF-IDF versus Lucene BM25

### 5.1 Evaluation objective

The purpose of the comparison was to investigate how the new Lucene implementation behaves relative to the existing TF-IDF retrieval configurations.

The comparison uses the same nine formal queries and the same BGG collection containing 17,648 documents.

The evaluated systems include:

- 30 TF-IDF configurations.
- One Lucene BGG-only BM25 configuration.

The Lucene implementation uses BM25 with \(k_1=1.2\) and \(b=0.75\).

The comparison is implemented in:

`experiments/retrieval/compare_tfidf_lucene.py`

### 5.2 Ranking comparison

For every query, the experiment compares the top-20 rankings produced by the TF-IDF configurations and Lucene BM25.

The comparison considers:

- **Top-10 overlap** – the number of common documents among the first ten results.
- **Top-20 overlap** – the number of common documents among the first twenty results.
- **Jaccard similarity** – the proportion of shared documents relative to the union of the compared result sets.
- **Spearman rank correlation** – the relationship between the rankings of common documents.
- **Kendall rank correlation** – another measure of agreement between the relative ordering of common documents.

The results are saved in:

`data/comparison_results/tfidf_vs_lucene/`

The generated files include:

- `rankings_long.tsv` – the combined rankings from the evaluated systems.
- `configuration_comparison.tsv` – comparisons between individual TF-IDF configurations and Lucene.
- `configuration_summary.tsv` – aggregated comparison results across queries.
- `manifest.json` – experiment metadata and validation information.

The comparison script also validates that the BGG-only and enriched Lucene indexes produce identical top-20 rankings and scores for the evaluated queries.

The current comparison uses `bgg_all_text`, which contains only BGG attributes. Therefore, the identical results are expected: Wikipedia-derived fields are not part of the evaluated query field.

This means the experiment compares the ranking behaviour of TF-IDF and BM25, but it does not demonstrate a retrieval improvement resulting from Wikipedia enrichment.

### 5.3 Relevance assessment

Ranking similarity alone does not establish whether the returned documents are relevant to the user's information need. A separate human relevance assessment was therefore prepared.

The assessment uses three relevance grades:

| Grade | Meaning |
|---:|---|
| 0 | Not relevant |
| 1 | Partially relevant |
| 2 | Highly relevant |

The original assessment pools were constructed from the top-20 results of the 30 TF-IDF configurations. To account for additional documents retrieved by Lucene, a separate extension was generated.

The extension is implemented in:

`experiments/retrieval/build_lucene_assessment_extension.py`

It processes all nine formal queries and both Lucene indexes, identifies documents absent from the original assessment pools, and creates additional assessment files. It also records the retrieval system and rank of each additional document in provenance files.

This preserves the original assessment data while ensuring that newly retrieved Lucene documents can be judged independently.

### 5.4 Completed Q01 relevance evaluation

The completed relevance evaluation currently covers Q01:

**Query:** `cooperative disease`

The evaluation combines the original Q01 judgments with the completed Lucene assessment extension. It evaluates 31 configurations:

- 30 TF-IDF configurations.
- One Lucene BGG-only BM25 configuration.

All top-10 results are required to have completed relevance judgments. The evaluation script checks this condition before calculating the metrics.

The following metrics are used:

**nDCG@10**

Normalized discounted cumulative gain evaluates the ordering of results while accounting for the three relevance grades. The gain function is:

\[
gain(rel) = 2^{rel} - 1
\]

Thus, the gains for grades 0, 1 and 2 are 0, 1 and 3, respectively. Higher-ranked relevant documents contribute more to the final score.

**Precision@10**

The proportion of the first ten results that are relevant. Grades 1 and 2 are considered relevant.

**Recall@10**

The proportion of all relevant documents in the completed Q01 assessment pool that appear in the first ten results.

The evaluation script reports the following Lucene BM25 result:

| Metric | Lucene BM25 |
|---|---:|
| nDCG@10 | 0.6814 |
| Precision@10 | 0.9000 |
| Recall@10 | 0.1731 |
| Relevant results in top 10 | 9 |
| Highly relevant results in top 10 | 6 |

For comparison, the best TF-IDF configuration for Q01 achieved:

| Metric | Best TF-IDF configuration |
|---|---:|
| nDCG@10 | 0.8528 |
| Precision@10 | 1.0000 |
| Recall@10 | 0.1923 |
| Relevant results in top 10 | 10 |
| Highly relevant results in top 10 | 7 |

The best TF-IDF configuration therefore achieved higher nDCG@10, precision and recall for this particular query.

These results are limited to Q01 and should not be interpreted as a general conclusion about all nine queries.

**Recall limitation:** Recall@10 is calculated against the relevant documents in the combined Q01 assessment pool of 64 judged documents. It is assessment-pool recall, not collection-wide recall.

The evaluation is implemented in:

`experiments/retrieval/evaluate_q01_relevance.py`

Its outputs include the relevance metrics, individual top-10 judgments and an evaluation manifest containing the input file fingerprints and evaluation details.

### 5.5 Interpretation and limitations

The experiments provide two complementary perspectives.

The nine-query ranking comparison measures how closely the retrieval systems agree in terms of the documents they return and their ordering. The Q01 relevance evaluation provides a direct assessment of retrieval quality using human judgments.

The Q01 results show that Lucene BM25 is capable of returning highly relevant results, but the best TF-IDF configuration performed better for this query according to the evaluated metrics.

The current experiments do not establish that either retrieval approach is universally superior. Only one query has completed relevance-based evaluation, while the ranking comparison covers all nine queries.

Similarly, the identical BGG-only and enriched rankings do not mean that the Wikipedia attributes are ineffective. They show that the current general-text comparison does not use those attributes. Further experiments targeting Wikipedia-derived fields, or incorporating them into a dedicated combined search field, would be necessary to evaluate their contribution to retrieval quality.

## 6. Direct answers to the Consultation 4 requirements

| Requirement | Implementation and evidence |
|---|---|
| Completed Spark processing and enriched data | Implemented and documented in Consultation 3 |
| Design and implementation of a PyLucene index | Two persistent indexes implemented in `src/lucene/` |
| Justification of individual index fields | Explained in Section 2.2 |
| Integration of the new index into the application | Command-line search application in `experiments/retrieval/search_lucene.py` |
| Comparison of old and new retrieval systems | Nine-query ranking comparison and Q01 relevance evaluation (See Section 5) |
| Types of queries supported | Boolean text, phrase, fuzzy and numeric range queries (Explained in Section 3) |
| GitHub repository | [https://github.com/FilipMojto/VAIV_Project.git] |

## 7. Execution and reproducibility

The index builder can be inspected using:

```bash
python3 -m src.lucene.builder --help
```

To build the indexes using the latest enriched dataset:

```bash
python3 -m src.lucene.builder \
    --source data/wiki_extracted/bgg_wikipedia_enriched_v3
```

The search application can be inspected using:

```bash
python3 experiments/retrieval/search_lucene.py --help
```

The ranking comparison and relevance evaluation are implemented in the `experiments/retrieval/` directory. Their input datasets, configuration details and generated outputs are retained separately from the persistent Lucene indexes.

The code and implementation history are maintained in the project's GitHub repository:

**Repository:** [Insert verified GitHub URL]

## 8. Conclusion

The consultation resulted in a working PyLucene indexing and retrieval implementation built on the enriched BGG dataset.

Two persistent indexes were created to separate the original BGG information from the additional Wikipedia-derived attributes. The index design distinguishes between searchable text, exact-value fields, numeric range fields and stored metadata. This provides a flexible structure for both retrieval and result presentation.

The search application supports Boolean text queries, phrase queries, fuzzy matching and numeric range filtering. It also allows the user to select between the BGG-only and enriched indexes and inspect the available Wikipedia metadata.

The evaluation compares Lucene BM25 against 30 TF-IDF configurations across nine formal queries. A separate human relevance assessment has been completed for Q01, where the best TF-IDF configuration outperformed Lucene BM25 on the reported metrics.

The results demonstrate the successful implementation and integration of the Lucene search system, while also identifying areas for further evaluation, particularly relevance assessment across all nine queries and experiments that explicitly incorporate Wikipedia-derived information into general retrieval.
