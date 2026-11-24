# Legacy Code

This directory contains older implementations and supporting code retained for historical reference.

These files are no longer part of the active application architecture. They are preserved to document previous development stages and allow comparison with their replacements.

## Archived implementations

### `baseline_indexers.py`

Contains the original BGG indexing implementation based on `BGGIndexer`.

It was superseded by the modular SQLite indexing implementation in `src/indexing/`, which separates index construction, database access, query processing, tokenization, and retrieval.

The archived implementation is retained for reference and is not imported by the active application.
