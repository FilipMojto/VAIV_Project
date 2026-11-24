# Apache Spark Processing Protocol: BoardGameGeek–Wikipedia Enrichment

## 1. Objective

The objective was to extend the existing BoardGameGeek (BGG) dataset with information extracted from Wikipedia. Apache Spark was used to process a Wikipedia XML dump, identify potentially relevant articles, resolve redirects, extract selected attributes, evaluate candidate matches, and integrate the resulting information into the original BGG dataset.

The implementation was designed as an offline data-processing pipeline. The computationally expensive Wikipedia processing is performed in advance, and the resulting datasets are stored in Parquet format for subsequent use by the search application.

The main objectives were:

- Identify Wikipedia articles corresponding to BGG games.
- Account for alternative game titles and Wikipedia redirects.
- Extract useful descriptive and game-specific attributes.
- Select the most relevant Wikipedia article for each BGG game.
- Enrich the original dataset without losing any BGG records.
- Preserve intermediate results to avoid repeatedly processing the original Wikipedia dump.

## 2. Processing architecture and rationale

The processing was divided into multiple stages to keep individual operations manageable, avoid unnecessary repeated processing, and make the matching process inspectable.

The main orchestration entry point is:

`src/scripts/extract_wikipedia_for_bgg.py`

The implementation separates Wikipedia page extraction and parsing from Spark-based processing and candidate evaluation.

### 2.1 Distributed Wikipedia extraction

**Approach:** Apache Spark with its Python API (PySpark).

The Wikipedia XML dump was processed using Spark rather than loading the entire dump into memory as one document.

A custom incremental XML page parser reconstructs individual Wikipedia page records from the input data. This allows pages to be processed independently while handling XML elements that can span input chunks.

The main extraction functionality is implemented in `src/wiki_spark_extraction.py`, with XML page parsing utilities in `src/wiki_extraction.py`.

**Rationale:** The Wikipedia dump is substantially larger than the BGG dataset. Incremental parsing and distributed processing make it possible to process the data in manageable partitions without requiring the entire dump to fit into memory.

### 2.2 Candidate identification and title matching

**Approach:** Match BGG game titles against Wikipedia article titles using generated title variants.

The matching process considers:

- Original BGG game titles.
- Alternative game names.
- Variants containing the suffixes `board game` and `game`.
- Relevant title and namespace information.

The implementation does not assume that the first title match is necessarily correct. Instead, it retains multiple candidate associations for subsequent evaluation.

The expanded candidate dataset contains **13,052 BGG–Wikipedia candidate associations**, representing **12,013 distinct Wikipedia candidate pages**.

**Rationale:** Board-game titles are not necessarily unique. A Wikipedia article may describe a different subject with the same name, while the relevant article may use a slightly different title. Retaining multiple candidates avoids prematurely discarding potentially correct matches.

### 2.3 Redirect resolution

**Approach:** Extract Wikipedia redirect targets and resolve them to their corresponding articles.

The redirect-processing stage creates a separate record for each distinct candidate Wikipedia page. It identifies whether a candidate redirects to another page and retrieves the target article information when resolution is possible.

The matching process distinguishes between:

- The original candidate page, which explains why the article was considered.
- The resolved target page, which may contain the actual article content and extracted metadata.

The original candidate title and page ID are preserved separately from the resolved target title and page ID.

**Rationale:** A candidate title may redirect to the actual article containing the information. Evaluating only the redirect page would result in missing attributes or incomplete matching evidence.

### 2.4 Attribute extraction using regular expressions

**Approach:** Extract selected information from Wikipedia article wikitext using regular expressions and supporting text-cleaning functions.

The extraction logic is implemented in `src/wiki_extraction.py`. It handles selected infobox templates, parameter aliases, and common formatting variations.

The final enriched dataset contains the following eleven Wikipedia attributes:

| Attribute | Description and purpose |
|---|---|
| `wiki_short_description` | A concise description useful for identifying and distinguishing a game. |
| `wiki_infobox_type` | The type of infobox used by the article, providing structural and classification information. |
| `wiki_designer` | The designer or designers associated with the game. |
| `wiki_publisher` | The publisher or publishers associated with the game. |
| `wiki_release_date` | Release-date information extracted from applicable non-game infoboxes. |
| `wiki_number_of_players` | The supported number or range of players, useful for filtering games by player count. |
| `wiki_playing_time` | The expected playing time, useful for comparing games and supporting search filters. |
| `wiki_publication_history` | Historical publication information, particularly useful for games whose infobox date describes multiple editions. |
| `wiki_setup_time` | The estimated time required to prepare a game. |
| `wiki_chance` | Information about the role of chance in gameplay. |
| `wiki_official_website` | The official website, providing an external reference for the game. |

**Date interpretation:** The implementation distinguishes between two different meanings of the Wikipedia infobox `date` parameter. For a game infobox, the information is extracted as `wiki_publication_history`. For other applicable infobox types, it is extracted as `wiki_release_date`.

This distinction prevents publication histories containing several edition years from being incorrectly treated as a single release date.

**Rationale:** These attributes provide complementary information. Descriptions and infobox types help identify and classify games, while designers and publishers provide attribution. Player count, playing time, and setup time are practical characteristics that can support search and filtering. Publication history provides temporal context, while chance describes a gameplay characteristic. An official website provides an additional external reference.

Wikipedia articles do not follow one completely uniform structure. The extractor therefore supports known infobox templates, parameter aliases, and selected formatting variations. Regular expressions provide a relatively lightweight extraction method without requiring a complete MediaWiki template parser.

### 2.5 Candidate ranking and selection

**Approach:** Assign a heuristic relevance score to each candidate and select the highest-ranked candidate for each BGG game.

The scoring considers three sources of evidence:

| Evidence | Score |
|---|---:|
| Primary title variant with `board game` | +5 |
| Alternate title variant with `board game` | +4 |
| Primary title variant with `game` | +3 |
| Alternate title variant with `game` | +2 |
| Primary original title | +1 |
| Alternate original title | +0 |
| Short description containing `board game` | +5 |
| Short description containing `game` | +2 |
| Infobox type equal to `game` | +4 |

For candidates involving redirects, the resolved target article's extracted metadata is used as matching evidence when available. If the target metadata is unavailable, the candidate page's own extracted metadata can be used as a fallback.

In the event of equal scores, direct articles are preferred over resolved redirects, followed by deterministic title and page-ID ordering.

All candidates are retained in the ranked output together with their scores and ranks. A separate boolean field identifies the selected candidate for each BGG game.

**Rationale:** Selecting candidates using multiple independent signals is more reliable than relying exclusively on title similarity. Retaining the ranking information also makes the selection process inspectable and allows incorrect or ambiguous matches to be investigated.

This is a heuristic approach rather than a semantic classifier. The highest-ranked candidate is not necessarily a correct match, especially when the available evidence is weak.

### 2.6 Final BGG–Wikipedia integration

**Approach:** Join the original BGG dataset with the selected Wikipedia candidates using the `app_id` field.

Before the final join, the selected candidate data is normalized to distinguish the original matching page from the actual article providing the extracted information.

The relevant fields distinguish:

- `wiki_matched_page_id` and `wiki_matched_title`: the original candidate page that matched a BGG title variant.
- `wiki_page_id` and `wiki_title`: the resolved target article, when a redirect was resolved, or the original article otherwise.
- `wiki_*` attributes: the extracted information associated with the selected article.

The final integration uses a **left outer join** from the original BGG dataset to the selected Wikipedia records on `app_id`.

The resulting Wikipedia attributes are stored in separate columns prefixed with `wiki_`. This prevents conflicts with existing BGG attributes, such as designer, publisher, and release year.

**Rationale:** BGG remains the primary dataset. Wikipedia provides supplementary information rather than replacing existing BGG data. A left outer join ensures that games without a suitable Wikipedia match remain present in the final dataset.

### 2.7 Intermediate storage

Intermediate and final processing results are stored in Parquet format.

The main processing outputs include:

| Dataset | Purpose | Records |
|---|---|---:|
| `bgg_wikipedia_matches_expanded` | Expanded BGG–Wikipedia candidate associations | 13,052 |
| `bgg_wikipedia_redirects` | Redirect-resolution records for distinct candidate pages | 12,013 |
| `bgg_wikipedia_fields_v5` | Extracted Wikipedia fields associated with candidate matches | 13,052 |
| `bgg_wikipedia_ranked_v3` | Ranked candidates, including the selected candidate per BGG game | 13,052 |
| `bgg_wikipedia_enriched_v3` | Final BGG dataset enriched with selected Wikipedia information | 17,648 |

**Rationale:** Parquet preserves column types, supports efficient columnar reads, and allows subsequent processing stages to reuse extracted data without reprocessing the original Wikipedia dump.

## 3. Demonstration of the BGG–Wikipedia join

The integration is based on the BGG `app_id` field. The matching process first produces candidate associations, then selects one candidate for each BGG game, and finally joins those selected records to the original BGG dataset.

The distinction between the different record counts is important:

1. The candidate-matching stage produces **13,052 candidate associations**. These are not 13,052 unique Wikipedia pages.
2. These associations refer to **12,013 distinct candidate Wikipedia page IDs**.
3. Candidate ranking selects one best candidate for each of **6,240 distinct BGG games**.
4. After redirect resolution, the selected records refer to **5,730 distinct Wikipedia target pages**.
5. The final left outer join preserves all **17,648 original BGG records**.

The difference between the 6,240 enriched BGG records and the 5,730 unique Wikipedia target pages means that some Wikipedia articles are associated with more than one BGG game.

### 3.1 Example: Catan

The game Catan provides a representative example of the complete process.

| Field | Result |
|---|---|
| BGG `app_id` | 13 |
| BGG game title | Catan |
| Original matched Wikipedia title | Catan (board game) |
| Resolved Wikipedia title | Catan |
| Matched title variant | `primary_board_game` |
| Redirect status | Resolved |
| Infobox type | game |
| Short description | Multi-player competitive board game |
| Designer | Klaus Teuber |
| Publishers | 17 extracted publisher entries |
| Release date | NULL |
| Publication history | First edition 1995; Second edition 1996; Third edition 1997; Fourth edition 2007; Fifth edition 2015; Sixth edition 2025 |
| Number of players | 3–4 (standard); 5–6 (with extensions) |
| Playing time | 1–2 hours |
| Setup time | 15 minutes |
| Chance | low-moderate |
| Official website | https://catan.com |

This example demonstrates why the pipeline preserves both the original candidate and the resolved target article. The BGG title matched the Wikipedia candidate `Catan (board game)`, which redirected to the article `Catan`. The target article supplied the extracted metadata.

It also demonstrates the distinction between `wiki_release_date` and `wiki_publication_history`: the game infobox contains a publication history covering multiple editions, rather than one single release date.

This is a representative end-to-end validation example, not proof that every Wikipedia article has been matched and extracted correctly.

## 4. Statistical results

### 4.1 Candidate matching and final integration

The latest successful processing run and subsequent audit produced the following results:

| Metric | Result |
|---|---:|
| Original BGG records | 17,648 |
| Candidate associations | 13,052 |
| Distinct candidate Wikipedia pages | 12,013 |
| Redirect-resolution records | 12,013 |
| Distinct BGG games with candidates | 6,240 |
| Selected candidates | 6,240 |
| Distinct Wikipedia target pages joined | **5,730** |
| BGG records enriched | 6,240 |
| BGG records without Wikipedia data | 11,408 |
| Final enriched dataset size | **17,648** |

The final join preserved the original number of BGG records. The audit found no duplicate `app_id` values in the selected candidate records or the original BGG dataset. The final join therefore did not introduce additional BGG rows.

The 12,013 redirect records correspond to the 12,013 distinct candidate Wikipedia pages, rather than the 13,052 candidate associations. Multiple BGG games can refer to the same candidate page.

Similarly, the final 5,730 distinct target pages count the actual Wikipedia articles supplying the selected information, not the original candidate associations.

### 4.2 Extracted attribute coverage

The following statistics were measured across the **6,240 BGG records with selected Wikipedia data**.

| Wikipedia attribute | Records containing a value | Coverage |
|---|---:|---:|
| Short description | 2,888 | 46.3% |
| Infobox type | 2,043 | 32.7% |
| Designer | 772 | 12.4% |
| Publisher | 901 | 14.4% |
| Release date | 349 | 5.6% |
| Number of players | 875 | 14.0% |
| Playing time | 783 | 12.5% |
| Publication history | 322 | 5.2% |
| Setup time | 458 | 7.3% |
| Chance | 555 | 8.9% |
| Official website | 225 | 3.6% |

The short description was the most frequently extracted attribute. Structured game-specific information, such as designer, publisher, player count, and playing time, was available less frequently. Setup time, chance, and official website were also extracted for a smaller subset of the selected articles.

These coverage figures describe the values successfully extracted from the selected articles using the implemented rules. They do not indicate whether the information is absent from Wikipedia itself. An article may contain relevant information in a structure or format that the current extractor does not recognize.

The release-date and publication-history figures should be interpreted separately because the implementation distinguishes between these two types of date information.

## 5. Validation and testing

The implementation was validated using unit tests, a representative real Wikipedia article, and an audit of the generated Spark datasets.

### 5.1 Extraction tests

The test suite in `testing/test_wiki_extraction.py` contains **33 passing tests** covering the implemented extraction functionality and supported variations in Wikipedia article formatting.

The Catan article was also used as a real-world extraction example. Its extracted attributes were checked against the expected article information.

### 5.2 Processing and integration audit

The successful end-to-end processing run generated the intermediate datasets and the final enriched dataset described above.

The subsequent audit verified:

- 13,052 expanded candidate associations.
- 12,013 distinct candidate Wikipedia page IDs.
- 12,013 redirect-resolution records.
- 13,052 extracted candidate associations.
- 13,052 ranked candidate associations.
- 6,240 selected BGG–Wikipedia matches.
- 17,648 records in the final enriched dataset.
- 5,730 distinct Wikipedia target pages in the final enriched dataset.
- No duplicate `app_id` values in the original BGG dataset or selected candidate records.
- No increase in the number of BGG records after the final join.

The audit also compared metadata extracted from the original candidate pages with metadata obtained from the resolved target articles. The target-article evidence contained additional nonempty values for some attributes:

| Attribute | Candidate-page values | Final evidence values |
|---|---:|---:|
| Setup time | 340 | 458 |
| Chance | 429 | 555 |
| Official website | 199 | 225 |
| Release date | 338 | 349 |
| Publication history | 308 | 322 |

These differences are expected because redirect targets can contain the actual article content, whereas the original candidate pages may contain little or no metadata. They demonstrate the benefit of using resolved target article information during candidate evaluation and final integration.

The validation provides evidence that the implemented pipeline works for the tested cases and preserves the required dataset structure. It does not establish that all Wikipedia article layouts or all candidate matches are correct.

## 6. Limitations and interpretation

Several limitations should be considered when interpreting the results:

1. **Title ambiguity:** Identical or similar titles can refer to unrelated subjects. The ranking heuristic reduces this problem but does not eliminate it.
2. **Variable article structure:** Wikipedia articles use different infobox templates, parameter names, and formatting conventions. The implemented regular expressions cover known patterns but cannot handle every possible structure.
3. **Incomplete attribute coverage:** Some articles do not contain the requested attributes, while others may store the information in formats not currently handled by the extractor. A missing extracted value therefore does not necessarily mean that the information is absent from the article.
4. **Heuristic candidate selection:** The highest-ranked candidate is selected even when the available evidence is weak. Consequently, some incorrect associations may remain.
5. **Redirect-resolution limitations:** Unusual or malformed redirects, unavailable target pages, or pages missing from the processed dump may prevent successful resolution.
6. **Value normalization:** Extracted values are not guaranteed to follow one consistent format. For example, dates, player ranges, and publisher names may require further normalization before being used for advanced filtering or comparison.
7. **Limited real-article validation:** The Catan example provides a representative end-to-end check, but it does not cover every possible Wikipedia article structure.

The results should therefore be interpreted as a first-pass enrichment of the BGG dataset, rather than a fully verified mapping between every BGG game and its corresponding Wikipedia article.

## 7. Direct answers to the Consultation 3 requirements

This section summarizes how the implementation addresses the main requirements of Consultation 3. Further technical details and evidence are provided in the referenced sections.

### 7.1 Justification and demonstration of the BGG–Wikipedia join

The datasets are joined using the BGG `app_id` field. A left outer join preserves all original BGG records while adding the attributes of the highest-ranked Wikipedia candidate. Candidate matching, redirect resolution, ranking, and the final join are described in Sections 2.2–2.6.

The Catan example in Section 3.1 demonstrates the complete process, including title matching, redirect resolution, and the extraction of attributes from the resolved article.

### 7.2 Number of unique Wikipedia pages joined

The ranking and selection stage produced matches for **6,240 BGG games**, referring to **5,730 distinct Wikipedia target pages**.

This figure represents the number of unique articles used in the selected matches, not the number of manually verified correct matches. Since the ranking algorithm always selects the highest-scoring candidate, some false-positive associations may remain. The matching statistics and their interpretation are discussed in Sections 3 and 4.1.
### 7.3 Interesting Wikipedia attributes

The implementation extracts eleven attributes: short description, infobox type, designer, publisher, release date, number of players, playing time, publication history, setup time, chance, and official website.

These attributes were selected because they provide complementary information about game identity, classification, authorship, publication, gameplay characteristics, and external references. Their individual purposes are described in Section 2.4, while their measured coverage is presented in Section 4.2.

## 7. Conclusion

The Spark processing pipeline successfully processed Wikipedia data, identified candidate articles for BGG games, resolved redirects, extracted eleven selected attributes, ranked candidate matches, and integrated the selected information into the original BGG dataset.

The final dataset contains **17,648 BGG records**, of which **6,240** were enriched using **5,730 distinct Wikipedia target pages**. The original BGG record count was preserved through the final left outer join.

The implementation also retains intermediate datasets and candidate-ranking information, making the processing stages reusable and the matching decisions inspectable.

The resulting Parquet dataset provides the enriched input for the subsequent PyLucene indexing and search implementation.
