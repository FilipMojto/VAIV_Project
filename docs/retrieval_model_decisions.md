# Retrieval-model selection: current rationale and experiment plan

Status: provisional. This document records the reasoning to guide the next experiment; it does not claim that the proposed models have already been implemented or evaluated.

## 1. Existing baseline

The custom `BGGIndexer` currently uses raw term frequency and supports two IDF options:

- classic IDF: \(\log(N/df_t)\);
- smoothed IDF: \(\log((N+1)/(df_t+1))+1\).

For each query term, the implementation adds `tf × idf` to matching document scores. The existing implementation therefore already satisfies the discussed minimum requirement of having at least two IDF calculation/ranking options, subject to confirming the official assignment wording and demonstrating the differences on at least three queries.

The existing implementation should be retained as a baseline while new methods are evaluated.

## 2. What the next phase should establish

The immediate goal is not to implement every formula in the lecture. It is to:

1. understand how each lecture-listed method changes weights;
2. compare their behaviour on the same small hypothetical documents;
3. select a defensible subset for the BGG indexer;
4. evaluate the selected methods on a fixed set of at least three queries;
5. preserve a clear distinction between the custom baseline and the Lucene comparison.

## 3. Candidate TF methods

The lecture's slide 47 lists:

1. natural TF;
2. logarithmic TF;
3. maximum-TF normalization;
4. Boolean TF;
5. log-average TF.

These methods should first be compared numerically using identical documents and term counts. Natural TF remains the existing baseline. Logarithmic TF is a strong candidate because it reduces the linear influence of repeated terms. Maximum-TF and log-average TF are alternatives that account for a document's internal frequency distribution. Boolean TF is a useful presence/absence comparison but discards frequency information.

No final choice should be made solely from the formula. The BGG descriptions and query results should determine whether a method is useful.

## 4. Candidate IDF methods

The lecture's slide 48 lists:

1. natural IDF: 1;
2. standard IDF: \(\log(N/df_t)\);
3. probabilistic IDF: \(\max(0,\log((N-df_t)/df_t))\).

The current custom indexer already has classic and smoothed IDF. The next phase should compare the lecture's IDF variants and explicitly demonstrate their behaviour for common terms.

Probabilistic IDF has a zero floor. A term whose document frequency is at least half the collection receives zero IDF. That term contributes zero to the total score, but other query terms can still produce a positive score. This is not a reason to assume the whole document score is always zero.

## 5. Normalization should be a separate experimental dimension

The lecture's slide 49 summarizes no normalization, Euclidean/cosine normalization and a byte/document-length normalization associated with Okapi BM25. Slide 46 explains why document length matters.

For BGG, document records can have different amounts of text. Euclidean normalization is therefore a justified candidate to test. However, the experiment should first isolate the effect of normalization from the effect of changing TF or IDF.

## 6. Proposed initial comparison set

The following is a practical starting proposal, not a final decision:

| Variant | TF | IDF | Normalization | Purpose |
|---|---|---|---|---|
| A — current baseline | Natural | Existing classic | None | Preserve current behaviour |
| B — existing alternative | Natural | Existing smoothed | None | Preserve current IDF comparison |
| C — lecture-inspired | Logarithmic | Standard | None initially, then test Euclidean separately | Evaluate diminishing returns from repetition |
| D — alternative TF | Maximum-TF or log-average | Standard | None initially | Compare document-relative TF weighting |
| E — lecture IDF alternative | Natural or selected TF | Probabilistic | Same normalization as control | Demonstrate zero-floor IDF behaviour |

The comparison should not expand into every possible Cartesian combination. Too many variants make it harder to explain which design choice caused a ranking change.

## 7. BM25 and the Lucene comparison

BM25 combines term-frequency saturation, an IDF component and document-length normalization. It is available through Lucene's similarity implementation and is the planned advanced ranking comparison for the PyLucene stage.

The current proposal is to avoid implementing BM25 in the custom Python baseline simply to duplicate Lucene's BM25. The custom indexer should provide transparent TF-IDF variants; Lucene should provide BM25 alongside the required query capabilities. If a later experiment needs to verify Lucene's BM25 implementation, a custom BM25 implementation could be useful as a validation exercise, but that is a separate research question.

Do not assume that two systems' BM25 rankings are directly comparable without aligning their analyzers, tokenization, fields, IDF details, parameters and document-length definitions.

## 8. Field weighting is a separate experiment

The current Python indexer concatenates title, alternate names, description and other metadata into one text field. Consequently, it cannot distinguish a title match from a match buried in a long description.

Field weighting could be valuable for BGG, but it should be introduced as a separate experiment after the TF/IDF comparison. Otherwise, a ranking improvement could be caused by field weights rather than the TF/IDF method being evaluated.

## 9. Evaluation protocol

Use the same dataset, tokenizer, query set and relevance judgments for each custom ranking variant. Include at least three queries to satisfy the discussed assignment requirement, but prefer a larger fixed set if time permits.

For every query:

- record the query text;
- define what makes a game relevant;
- inspect and save the top-ranked results for each model;
- compare ranking changes, not just whether a document appears somewhere in the results;
- calculate Precision@k, Recall@k, MAP or NDCG only where the relevance judgments support those metrics;
- explain notable cases, including common query terms with zero or very low IDF.

## 10. Presentation defence: core rationale

A defensible explanation should connect each method to a property of the collection:

- Natural TF is retained as a simple baseline because it is transparent and easy to interpret.
- Logarithmic TF is tested because repeated mentions should not necessarily contribute linearly to relevance.
- Standard/smoothed IDF distinguish terms by how widely they occur across the collection.
- Probabilistic IDF is included as a lecture-taught alternative, with its zero-floor effect explained.
- Euclidean normalization is tested because BGG records differ in length.
- BM25 is evaluated separately in Lucene as a more advanced ranking model combining TF saturation, IDF and length normalization.

The final selection must be supported by measured behaviour on the BGG query set. Do not claim that a method is better merely because it is more sophisticated or appears in a lecture.
