# Relevance Assessment Protocol

## 1. Purpose

This document defines the procedure for assigning relevance judgements to the formal evaluation queries used in the BGG board-game information retrieval experiment.

The objective is to establish consistent, query-specific relevance judgements independently of the ranking configurations being evaluated.

The assessment results will subsequently be used to compare the retrieval quality of the 30 TF-IDF configurations.

## 2. Assessment dataset

The assessment pools were generated from the top 20 results returned by each of the 30 ranking configurations for each formal query.

| Property | Value |
|---|---:|
| Formal queries | 9 |
| Ranking configurations | 30 |
| Results per configuration | 20 |
| Maximum result appearances per query | 600 |
| Unique games across all queries | 712 |

The resulting assessment dataset consists of nine TSV files in:

`data/assessment/formal_evaluation/`

Each file contains the following information:

- `assessment_id`: unique identifier for the assessment record.
- `app_id`: original BoardGameGeek application identifier.
- `game_title`: board-game title.
- `release_year`: publication year.
- `short_description`: short game description.
- `description`: longer game description.
- `game_type`: game type information.
- `game_category`: BGG categories.
- `game_mechanic`: BGG mechanics.
- `designer`: designer information.
- `publisher`: publisher information.
- `relevance_grade`: field to be completed during assessment.

Each game appears only once within a query's assessment pool, even if multiple ranking configurations retrieved it.

## 3. Relevance scale

Three relevance grades are used.

| Grade | Classification | Definition |
|---:|---|---|
| 2 | Highly relevant | The game clearly satisfies the central intent of the query. Its theme, mechanics or gameplay characteristics strongly match the requested concept. |
| 1 | Partially relevant | The game has a meaningful connection to the query, but satisfies only part of its intent or represents a weaker interpretation. |
| 0 | Not relevant | The game does not meaningfully satisfy the query's intent, even if some words or concepts overlap. |

### Grade 2 – Highly relevant

Assign grade 2 when the game is a strong example of what the query describes.

The relevant characteristics should be central or substantial parts of the game's identity or gameplay.

A game does not need to match every word literally if its overall characteristics clearly satisfy the query.

### Grade 1 – Partially relevant

Assign grade 1 when the game has a genuine but incomplete connection to the query.

Examples include:

- A game matches the requested theme but not the requested gameplay mechanic.
- A game uses the requested mechanic, but it is relatively peripheral rather than central.
- A game satisfies one part of a multi-concept query but not the others.
- A game represents a reasonable but less direct interpretation of the query.

Grade 1 should not be used merely because a game contains a matching word in its description.

### Grade 0 – Not relevant

Assign grade 0 when the game does not meaningfully match the query.

Examples include:

- A game shares a keyword but has a different theme or gameplay purpose.
- A game mentions a concept incidentally without actually implementing it.
- A game matches only a superficial association.
- The game does not satisfy the intended combination of concepts.

## 4. Query-specific interpretation

The following interpretations define the intended scope of each formal query.

| ID | Query | Intended relevance |
|---|---|---|
| Q01 | cooperative disease | Cooperative games involving disease, epidemics, infection or disease-control themes. |
| Q02 | medieval economic strategy | Strategy games with medieval settings and meaningful economic development, production, trade or resource management. |
| Q03 | space exploration | Games centred on exploring space, planets, star systems or the wider universe. |
| Q04 | deck building fantasy | Fantasy games in which deck-building is an important gameplay mechanic. |
| Q05 | hidden role deduction | Games involving hidden identities or roles where players use deduction, information or behavioural clues to identify others. |
| Q06 | civilization development | Games focused on developing, expanding or managing a civilization through mechanisms such as technology, culture, economy or territorial growth. |
| Q07 | train route building | Games involving railway or train networks, route construction or the development of transportation networks. |
| Q08 | negotiation trading | Games where negotiation, bargaining, deal-making or player-to-player trading are meaningful gameplay elements. |
| Q09 | solo adventure campaign | Adventure games that support solo play and offer campaign-style progression or connected scenarios. |

The query should be interpreted as a complete concept rather than as a collection of independent keywords.

For example, Q04 requires both a fantasy context and meaningful deck-building gameplay. A fantasy game without deck-building should not automatically receive a high relevance grade.

Likewise, Q09 requires both solo support and campaign-style adventure progression. A game that supports solo play but has no meaningful campaign structure is not a strong match.

## 5. Assessment procedure

For each assessment record:

1. Read the game title and available descriptive information.
2. Examine the short and long descriptions.
3. Consider the available categories and mechanics.
4. Compare the actual game characteristics against the intended meaning of the corresponding query.
5. Assign one relevance grade: 0, 1 or 2.
6. Enter the grade in the `relevance_grade` column.

The judgement must be based on the game's characteristics, not on the fact that it was retrieved by a particular search configuration.

### Evidence hierarchy

Use the available evidence in the following order:

1. Actual gameplay and theme described in the game description.
2. Explicitly listed game mechanics and categories.
3. Short description and other supporting metadata.
4. Game title, only as supporting evidence.

A matching title or keyword alone is insufficient to establish relevance.

If the supplied information is insufficient to establish a meaningful connection, do not assume that the game is relevant simply because the retrieval system returned it.

If additional information is needed, consult the game's BoardGameGeek entry to clarify its mechanics or theme. Apply this consistently rather than researching only games that initially seem relevant.

## 6. Consistency and assessment controls

The following rules must be maintained throughout the assessment:

- Assess every game independently for each query.
- Use the same relevance definitions for all nine queries.
- Do not inspect ranking configurations, retrieval scores or original result positions during assessment.
- Do not change the intended query meanings to accommodate particular retrieved games.
- Do not assign relevance based solely on keyword overlap.
- Do not assume that popular or highly rated games are more relevant.
- Do not assume that a game is relevant because it appears in many configurations.
- Do not change previously assigned grades merely because later games produce different interpretations of the query.

A game can receive different grades for different queries. Relevance is always assessed in relation to the particular query, not as an overall property of the game.

## 7. Handling ambiguous cases

Some games may be difficult to classify because their descriptions are incomplete, their mechanics are unusual or their connection to a query is indirect.

In such cases:

1. Reconsider the complete query definition.
2. Examine the available game information.
3. Determine whether the connection is central, partial or merely superficial.
4. Apply the three-grade scale consistently.

Do not create additional relevance grades.

If an assessment remains genuinely uncertain, record the assessment ID separately for later review rather than silently changing the grading criteria.

## 8. Blinding and provenance

The assessment TSV files intentionally exclude:

- Ranking configuration names.
- Original retrieval positions.
- Retrieval scores.
- Other information that could reveal which configurations retrieved a game.

The corresponding provenance JSON files preserve this information separately.

Provenance must not be consulted during relevance assessment. It will be used after the judgements have been completed to reconstruct the original rankings and calculate evaluation metrics.

The `assessment_id` provides the link between an assessed game and its provenance record.

## 9. Evaluation metrics

After all relevance judgements have been completed, the grades will be combined with the original ranking results.

The planned evaluation metrics are:

- **Precision@10:** proportion of the top ten results considered relevant. Grades 1 and 2 count as relevant.
- **Recall@10:** proportion of all relevant games in the judged pool retrieved in the top ten. This is pool-based recall, not guaranteed collection-wide recall.
- **nDCG@10:** ranking-quality metric that considers both relevance and result position.

For nDCG, the gain values are:

| Relevance grade | Gain |
|---:|---:|
| 0 | 0 |
| 1 | 1 |
| 2 | 3 |

The discount is based on the logarithm of the result position.

Metrics will first be calculated separately for each query and configuration. Macro-averages across the nine queries will then give each query equal weight.

nDCG@10 is the primary quality metric. Precision@10 and Recall@10 provide complementary information.

Execution time is a secondary consideration and will be used mainly when retrieval quality is comparable.

## 10. Completion and validation

Before evaluation:

- All nine assessment files must contain a relevance grade for every record.
- Grades must be restricted to 0, 1 or 2.
- Each assessment ID must remain unchanged.
- Each app ID must remain associated with its original assessment record.
- The provenance files must remain unchanged.
- The completed assessment files must be validated before metric calculation.

The original ungraded assessment files should be preserved as the baseline assessment pools. Completed judgements should be stored separately so that the original generated pools remain reproducible.

---

**End of protocol**