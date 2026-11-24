# Lecture notes: TF, IDF and document normalization

Source: `06_seleng_ir_indexovanie.pdf`, lecture presentation *Vyhľadávanie Informácií*, especially slides 44–49, 50–56 and 63. These notes summarize the formulas and explanations shown in that presentation. Explanatory comments and project-specific recommendations are identified as such.

## 1. Three separate parts of term weighting

A basic TF-IDF term weight can be written as:

\[
w_{t,d}=TF(t,d)\cdot IDF(t)
\]

where:

- \(t\) is a term;
- \(d\) is a document;
- \(TF(t,d)\) describes the term's frequency/weight within the document;
- \(IDF(t)\) describes how informative the term is across the collection.

Document normalization is a further operation that can adjust document weights or the document vector. TF, IDF and document normalization address related but distinct issues and should not be treated as interchangeable.

## 2. TF modifications — slide 47

Let:

- \(tf_{t,d}\) be the raw number of occurrences of term \(t\) in document \(d\);
- \(tf_{max}(d)\) be the maximum term frequency in document \(d\);
- \(\alpha\) be the maximum-TF scaling coefficient (the preceding slide gives 0.5 as a standard value).

### 2.1 Natural TF

\[
TF(t,d)=tf_{t,d}
\]

The weight is the raw occurrence count. Each additional occurrence increases the weight linearly.

### 2.2 Logarithmic TF

\[
TF(t,d)=
\begin{cases}
1+\log(tf_{t,d}) & tf_{t,d}>0\\
0 & tf_{t,d}=0
\end{cases}
\]

Slide 44 motivates this by asking whether a term occurring 20 times should have 20 times the influence of a term occurring once. Logarithmic scaling reduces the marginal effect of repeated occurrences while retaining frequency information.

The lecture does not require a particular logarithm base in the summary formula. A base should be selected and used consistently in an implementation.

### 2.3 Maximum-TF normalization

\[
TF(t,d)=\alpha+(1-\alpha)\frac{tf_{t,d}}{tf_{max}(d)}
\]

This compares a term's frequency with the most frequent term in the same document. Slide 45 says it addresses cases where a very frequent word overwhelms other terms, including repetition-based manipulation. It also notes that this method does not solve every issue, including sensitivity to changes in the stop-word vocabulary.

### 2.4 Boolean TF

\[
TF(t,d)=
\begin{cases}
1 & tf_{t,d}>0\\
0 & tf_{t,d}=0
\end{cases}
\]

Only presence or absence matters. A term occurring once and a term occurring many times receive the same TF weight.

This is a term-weighting scheme. It should not be confused with the Boolean retrieval model, which uses logical operators such as AND, OR and NOT to determine matching documents.

### 2.5 Log-average TF

\[
TF(t,d)=\frac{1+\log(tf_{t,d})}{1+\log\left(avg_{t\in d}(tf_{t,d})\right)}
\]

The denominator uses the average term frequency in the document. Thus, a term's transformed frequency is considered relative to the average frequency of terms in that document. The exact averaging/token population must be defined consistently in an implementation.

## 3. IDF modifications — slide 48

Let:

- \(N\) be the number of documents in the collection;
- \(df_t\) be the number of documents containing term \(t\).

### 3.1 Natural IDF

\[
IDF(t)=1
\]

All terms receive the same IDF multiplier. This effectively removes inverse-document-frequency discrimination.

### 3.2 Standard IDF

\[
IDF(t)=\log\left(\frac{N}{df_t}\right)
\]

A term appearing in fewer documents receives a higher weight. A term appearing in every document receives IDF zero. The lecture notes that the logarithm base may be chosen (base 10 is given as a standard example); the base affects scale, not the ordering of IDF values, when used consistently.

### 3.3 Probabilistic IDF

\[
IDF(t)=\max\left\{0,\log\left(\frac{N-df_t}{df_t}\right)\right\}
\]

This variant has a zero floor. If a term appears in at least half the documents, the logarithmic expression is non-positive and the resulting IDF is zero.

**Important scoring consequence:** If one query term has IDF zero, its own TF×IDF contribution is zero. It does not automatically make the entire document score zero, because the document score is normally the sum of contributions from query terms:

\[
Score(q,d)=\sum_{t\in q}TF(t,d)\cdot IDF(t)
\]

A document can still receive a positive score from other query terms whose IDF values are positive. Its total score becomes zero only if all matching query-term contributions are zero (or there are no positive matching contributions).

Slide 63 separately discusses the negative-IDF issue in the Okapi BM25 context and lists possible treatments such as a zero minimum, a small positive minimum, or a different strictly positive IDF function.

## 4. Document-length normalization — slides 45, 46 and 49

### 4.1 No normalization

The normalization factor is 1. No document-length correction is applied.

### 4.2 Euclidean / cosine normalization

For a document vector with term weights \(w_1,w_2,\ldots,w_n\), its Euclidean length is:

\[
\|d\|_2=\sqrt{w_1^2+w_2^2+\cdots+w_n^2}
\]

The normalized term weights are:

\[
w'_{i}=\frac{w_i}{\|d\|_2}
\]

Slide 46 explains that this accounts for document length and that it also addresses the issue of repeating an entire document. Slides 55–56 connect vector normalization with cosine similarity.

### 4.3 Byte/length normalization shown with Okapi BM25

Slide 49 gives a length-based factor of the form:

\[
\frac{1}{DocumentCharLength^\alpha},\qquad \alpha<1
\]

and labels it as the byte normalization used in Okapi BM25. The exact implementation details and parameterization should be taken from the BM25 formula/implementation rather than treating this isolated factor as a complete BM25 model.

## 5. Worked example and vector-space model

Slides 50–51 demonstrate document scoring by summing query-term and document-term weights. The example uses TF-IDF for query weights, logarithmic TF for document weights and Euclidean normalization of the document vector. It illustrates that ranking depends on the combination of query weights and document weights, not on raw TF alone.

Slides 52–56 introduce the vector-space model:

- each document is represented as a vector of term weights;
- the collection forms a vector space in which terms correspond to dimensions;
- the query can also be represented as a vector;
- cosine similarity compares the direction of the vectors, reducing sensitivity to their absolute lengths.

## 6. Okapi BM25 — slide 63

The lecture introduces Okapi BM25 as a ranking function with document-length adjustment and discusses the issue that an IDF expression can become negative when a term appears in more than half the documents. It lists possible remedies, including setting a lower bound of zero or a small positive value.

BM25 is a complete ranking model, not merely another name for probabilistic IDF. It combines term-frequency saturation, an IDF component and document-length normalization. The exact formula and parameter values should be documented from the implementation used in the project.

## 7. How these concepts relate to the BGG project

The current custom Python indexer uses raw TF and two IDF variants (classic and smoothed). It sums term contributions and does not currently normalize document vectors by length. It also combines several BGG text fields into one text representation.

The collection contains records with different amounts of textual metadata. This gives a concrete reason to investigate document-length normalization. Repeated terms can also occur in descriptions, which gives a reason to compare natural and logarithmic TF.

A sensible experimental sequence is:

1. Preserve the existing implementation as the baseline.
2. Compare the lecture's TF variants using a small controlled numerical example.
3. Compare the lecture's IDF variants, including the zero-floor behaviour of probabilistic IDF.
4. Evaluate normalization separately so that the effect of each change can be understood.
5. Select only a small number of methods for the final custom indexer and justify them with the BGG data and query results.

BM25 is planned as a separate Lucene comparison. Implementing the same BM25 ranking in both the custom baseline and Lucene would not provide a useful model-level comparison unless the explicit purpose were to compare two implementations of BM25.

## 8. Source boundary

The formulas and slide-specific explanations above are based on the supplied lecture presentation. The BGG-specific experimental recommendations are project analysis, not claims made by the lecturer. Where the presentation's extracted text or equation rendering is ambiguous, the original slide image should be treated as authoritative.
