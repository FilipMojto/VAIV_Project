# Apache Spark Processing Protocol: BoardGameGeek–Wikipedia Enrichment

## 1. Objective

The objective was to extend the existing BoardGameGeek (BGG) dataset with information extracted from Wikipedia. Apache Spark was used to process the Wikipedia XML dump, identify potentially relevant articles, extract selected attributes, and integrate the resulting information into the original BGG dataset.

The implementation was designed as an offline data-processing pipeline. The expensive Wikipedia dump processing is performed in advance, and the resulting datasets are stored in Parquet format for subsequent use by the search application.

## 2. Processing architecture and rationale

The processing was divided into several stages to avoid repeatedly processing the large Wikipedia dump and to keep individual operations manageable.

### 2.1 Distributed Wikipedia extraction

**Approach:** Apache Spark with its Python API (PySpark).

The Wikipedia XML dump was processed using Spark rather than loading the entire dump into memory or parsing it as one large document.

A custom incremental XML page parser was used to reconstruct individual Wikipedia page records from the input data. This allowed pages to be processed independently while handling XML elements that could span input chunks.

**Rationale:** The Wikipedia dump is substantially larger than the BGG dataset. Distributed processing makes it possible to process the data in partitions and provides a scalable approach to extracting relevant pages.

### 2.2 Candidate identification and title matching

**Approach:** Match BGG game titles against Wikipedia article titles using generated title variants.

The matching process considered:
- Original BGG game titles.
- Alternate game names.
- Variants containing the suffixes "board game" and "game".
- Relevant title and namespace information.

Instead of assuming that every title match represents the correct article, the process retained multiple candidates for subsequent evaluation.

**Rationale:** Board-game titles are not necessarily unique. A Wikipedia article may describe a different subject with the same name. Retaining candidates avoids prematurely discarding potentially correct matches.

### 2.3 Redirect resolution

**Approach:** Extract redirect targets and resolve them to their corresponding Wikipedia pages.

Resolved redirects were retained as candidate associations, but the target article's metadata was used when evaluating their relevance.

**Rationale:** A candidate title may redirect to the actual article containing the information. Evaluating only the redirect page would result in missing attributes or incomplete matching evidence.

### 2.4 Attribute extraction using regular expressions

**Approach:** Extract selected information from Wikipedia article wikitext using regular expressions and supporting text-cleaning functions.

The extracted attributes included:

- Short description
- Infobox type
- Designer
- Publisher
- Release/publication date
- Number of players
- Playing time

The extraction process also handles selected variations in infobox parameter names and simple nested templates.

**Rationale:** Wikipedia articles do not follow one completely uniform structure. Parameter aliases and template variations therefore need to be considered. Regular expressions provide a lightweight method for extracting the required information without implementing a complete MediaWiki template parser.

### 2.5 Candidate ranking

**Approach:** Assign a heuristic relevance score to each candidate and select the highest-ranked candidate for each BGG game.

The scoring considers three sources of evidence:

| Evidence | Score |
|---|---:|
| Primary title variant with "board game" | +5 |
| Alternate title variant with "board game" | +4 |
| Primary title variant with "game" | +3 |
| Alternate title variant with "game" | +2 |
| Primary original title | +1 |
| Alternate original title | +0 |
| Short description containing "board game" | +5 |
| Short description containing "game" | +2 |
| Infobox type equal to "game" | +4 |

Resolved redirects use the target article's extracted metadata as evidence. In the event of equal scores, direct articles are preferred over resolved redirects, followed by deterministic title and page-ID ordering.

All candidates are retained in the ranked output, together with their scores and ranks. The best candidate is identified using a separate boolean field.

**Rationale:** Selecting candidates using multiple independent signals is more reliable than relying exclusively on title similarity. Retaining the ranking information also makes the selection process inspectable.

This is a heuristic approach rather than a semantic classifier. The highest-ranked candidate is not necessarily a correct match.

### 2.6 Final BGG–Wikipedia integration

**Approach:** Join the original BGG dataset with the selected Wikipedia candidates using the `app_id` field.

The final join uses a left outer join, preserving all original BGG records, including games without a Wikipedia match.

Wikipedia attributes are stored in separate columns prefixed with `wiki_`, preventing conflicts with existing BGG attributes such as designer, publisher, and release year.

**Rationale:** The original BGG information remains the primary dataset. Wikipedia provides supplementary information rather than replacing existing BGG data.

### 2.7 Intermediate storage

Intermediate and final processing results are stored in Parquet format.

**Rationale:** Parquet preserves column types, supports efficient columnar reads, and allows subsequent processing stages to reuse extracted data without reprocessing the original Wikipedia dump.

## 3. Statistical results

### 3.1 Candidate matching and final integration

| Metric | Result |
|---|---:|
| Original BGG records | 17,648 |
| Candidate associations | 13,052 |
| Distinct BGG games with candidates | 6,240 |
| Selected candidates | 6,240 |
| Distinct Wikipedia target pages joined | **5,730** |
| BGG records enriched | 6,240 |
| BGG records without Wikipedia data | 11,408 |
| Final enriched dataset size | 17,648 |

The difference between the 6,240 enriched BGG records and the 5,730 unique Wikipedia pages means that some Wikipedia pages were associated with more than one BGG record.

The final join preserved the original number of BGG records. No duplicate join keys were detected in either the original BGG dataset or the selected Wikipedia candidates.

### 3.2 Extracted attribute coverage

The following statistics were measured across the 6,240 BGG records with selected Wikipedia data.

| Wikipedia attribute | Records containing a value | Coverage |
|---|---:|---:|
| Short description | 2,888 | 46.3% |
| Infobox type | 2,043 | 32.7% |
| Designer | 772 | 12.4% |
| Publisher | 901 | 14.4% |
| Release/publication date | 796 | 12.8% |
| Number of players | 875 | 14.0% |
| Playing time | 783 | 12.5% |

The short description was the most frequently extracted attribute. Structured game-specific information, such as designer, publisher, player count, and playing time, was available less frequently.

These coverage figures reflect the selected articles and the implemented extraction rules, not the overall availability of these attributes across every Wikipedia article.

## 4. Limitations and interpretation

Several limitations should be considered when interpreting the results:

1. **Title ambiguity:** Identical or similar titles can refer to unrelated subjects. The ranking heuristic reduces this problem but does not eliminate it.
2. **Variable article structure:** Wikipedia articles use different infobox templates and parameter names. Some information is therefore not extracted by the implemented rules.
3. **Incomplete attribute coverage:** Many selected articles do not contain all the requested attributes, or store information in formats not currently handled by the extractor.
4. **Heuristic candidate selection:** The highest-ranked candidate is selected even when the available evidence is weak. Consequently, some incorrect associations remain possible.
5. **Value normalization:** Extracted values are not guaranteed to follow one consistent format. For example, dates and publisher names may require further normalization.

The results should therefore be interpreted as a first-pass enrichment of the BGG dataset, rather than a fully verified mapping between every BGG game and its corresponding Wikipedia article.

## 5. Conclusion

The Spark processing pipeline successfully extracted and processed Wikipedia data, identified candidate articles, resolved redirects, extracted selected article attributes, ranked candidate matches, and integrated the selected information into the original BGG dataset.

The final dataset contains 17,648 BGG records, of which 6,240 were enriched using 5,730 distinct Wikipedia pages.

The resulting Parquet dataset provides the enriched input for the subsequent PyLucene indexing and search implementation.
