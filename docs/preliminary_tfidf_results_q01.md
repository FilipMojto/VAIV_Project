# Preliminary TF–IDF Experiment Results and Configuration Selection

**Date:** 21 November 2026
**Status:** Preliminary selection based on Q01; evaluation of the remaining queries is pending.

## 1. Purpose

The initial TF–IDF experiment compared 30 configurations formed from five term-frequency (TF) methods, three inverse document-frequency (IDF) methods and two document-normalisation settings.

The purpose of this preliminary evaluation was to identify promising configurations for subsequent implementation and integration work.

## 2. Evaluation basis

The first formal evaluation query was:

- **Q01:** `cooperative disease`

The relevance assessment pool contained 63 unique games. All 63 documents were assessed using the agreed three-level relevance scale:

- 2 — highly relevant
- 1 — partially relevant
- 0 — not relevant

The assessment contained 11 highly relevant, 41 partially relevant and 11 irrelevant games.

The primary evaluation metric was nDCG@10. Precision@10 and pool-based Recall@10 were also considered.

## 3. Selected configurations

Two configurations were selected for further implementation and evaluation:

| Configuration | Precision@10 | Recall@10 | nDCG@10 |
|---|---:|---:|---:|
| Logarithmic TF + Smoothed IDF + Euclidean normalisation | 1.00 | 0.192 | **0.853** |
| Maximum TF + Classic IDF + Euclidean normalisation | 1.00 | 0.192 | **0.817** |

### Configuration 1: Logarithmic TF + Smoothed IDF + Euclidean normalisation

This was the highest-performing configuration in the Q01 evaluation, achieving an nDCG@10 of approximately 0.853. All ten retrieved results were relevant.

It was therefore selected as the primary configuration.

### Configuration 2: Maximum TF + Classic IDF + Euclidean normalisation

This configuration achieved an nDCG@10 of approximately 0.817, making it a strong alternative. It was also the best-performing configuration among those using Classic IDF.

It was selected to retain a second IDF approach while maintaining strong ranking quality.

## 4. Rationale

The preliminary results indicate that Smoothed IDF performs particularly well for Q01. However, selecting only configurations using Smoothed IDF would not demonstrate the use of multiple IDF methods.

The selected pair therefore provides a practical balance:

- Both configurations achieve perfect Precision@10.
- Both use Euclidean document normalisation.
- They demonstrate two different TF methods: logarithmic and maximum TF.
- They demonstrate two different IDF methods: Smoothed and Classic IDF.
- Both achieve strong nDCG@10 results.

This selection also avoids choosing a substantially weaker configuration solely to demonstrate methodological variety.

## 5. Limitations

These findings are preliminary and are based exclusively on Q01 (`cooperative disease`). They do not establish that the selected configurations will perform best across all evaluation topics.

The remaining eight queries will be used to assess whether the observed performance differences generalise to other subject areas. The final comparison should use macro-averaged nDCG@10 across all nine queries, giving each query equal weight.

Recall@10 is calculated against the relevant documents in the assessed Q01 pool, rather than against every potentially relevant game in the full BGG collection. It should therefore be interpreted as pool-based recall.

## 6. Preliminary decision

For the next implementation stage, the two selected configurations are:

1. **Logarithmic TF + Smoothed IDF + Euclidean normalisation**
2. **Maximum TF + Classic IDF + Euclidean normalisation**

These configurations will serve as the current working selection for the subsequent Spark and Lucene implementation stages. The selection may be revisited after the remaining relevance assessments have been completed.
