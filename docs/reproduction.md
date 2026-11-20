# Development environment and reproduction guide

Last verified: 2026-11-20

This guide records the environment in which the Spark and PyLucene smoke tests passed. It is a reproducibility record, not a promise that every dependency can be installed identically on every Linux distribution.

## 1. Verified environment

| Component | Verified version / value |
|---|---|
| Operating environment | WSL 2, Ubuntu 26.04 / Resolute |
| Python | 3.11.18 |
| Python environment | `~/vinfproj/.venv-wsl` |
| Java | OpenJDK 17.0.21.1 |
| `JAVA_HOME` | `/usr/lib/jvm/java-17-openjdk-amd64` |
| Apache Ant | 1.10.15 |
| JCC | 3.14, non-shared build |
| PyLucene | 9.12.0 |
| PySpark | 4.3.0 |

The exact versions should be rechecked when reproducing this setup. PyLucene versions are tied to compatible Lucene, JCC, Java and Python versions.

## 2. Python virtual environment

The verified environment was created with `uv` and used Python 3.11.18. The following is an example for a fresh environment; adapt the project path and Python installation to the machine being configured.

```bash
{
    cd "$HOME/vinfproj"
    uv venv --python 3.11 .venv-wsl
    source .venv-wsl/bin/activate
    python --version
} 2>&1 | tee /dev/tty | clip.exe
```

The project currently has a `requirements.txt` containing the scraping/testing/demo dependencies. PySpark and PyLucene were installed separately during the environment setup described here. Before using a clean environment for the whole project, reconcile the dependency declarations with the actual imports and decide which dependencies are core, optional, development-only or platform-specific.

## 3. Dependency management: uv, Pipenv and requirements.txt

`pip`, `uv` and Pipenv do not all update every dependency file automatically.

- **pip:** installs packages into the active environment. It does not automatically rewrite `requirements.txt`.
- **uv with `pyproject.toml`:** dependencies should be declared in the project configuration; `uv add` can update the project declaration and lockfile. `uv sync` installs from the project metadata/lockfile. A requirements file can be exported when needed.
- **Pipenv with `Pipfile`:** dependencies are declared in `Pipfile`; `pipenv install` updates the declaration and lockfile. `requirements.txt` is not automatically maintained as a synchronized second source of truth.
- **requirements.txt:** is commonly a manually maintained or exported pip-compatible dependency list. Installing from it does not update it.

The repository's authoritative dependency workflow should be chosen explicitly. Avoid maintaining `requirements.txt`, `pyproject.toml` and `Pipfile` as independent editable sources of truth. If `uv` is adopted, a `pyproject.toml` plus `uv.lock` is a suitable primary workflow; `requirements.txt` can be generated for environments that need it.

PyLucene is a special case. A simple package declaration may document the required version, but a successful installation also depends on a compatible native build toolchain. The build instructions below are therefore essential.

## 4. PySpark verification

PySpark 4.3.0 was installed in the virtual environment. The following local smoke test passed:

```python
from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .master("local[2]")
    .appName("vinf-smoke-test")
    .getOrCreate()
)

print("Spark version:", spark.version)
spark.range(5).show()
print("Number of rows:", spark.range(5).count())
spark.stop()
```

Expected key output:

- Spark version: `4.3.0`
- rows with IDs 0 through 4;
- count: `5`.

This test verifies local Spark execution only. It does not verify the Wikipedia dump parsing, regex extraction, BGG join or output reporting.

## 5. PyLucene build environment

### 5.1 Compatibility used

The project built PyLucene 9.12.0 with Java 17 and JCC 3.14. PyLucene 10 was not used because it requires a newer Java/JCC toolchain. The source distribution included the matching Lucene Java sources and JCC version.

### 5.2 System build tools

The verified system had:

- OpenJDK 17 development headers and JVM libraries;
- `ant` 1.10.15;
- `gcc`, `g++`, `make`, `javac` and `curl`;
- Python 3.11 development headers corresponding to the active interpreter.

The JDK must include the JNI headers and JVM libraries. Merely having a Java runtime is insufficient for building the Python extension.

### 5.3 Environment variables used for JCC

The build used the following environment configuration (the paths reflect the verified WSL machine):

```bash
{
    export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
    export JCC_JDK="$JAVA_HOME"
    export JCC_ARGSEP=';'
    export JCC_INCLUDES="$JAVA_HOME/include;$JAVA_HOME/include/linux"
    export JCC_LFLAGS="-L$JAVA_HOME/lib;-ljava;-L$JAVA_HOME/lib/server;-ljvm;-Wl,-rpath=$JAVA_HOME/lib:$JAVA_HOME/lib/server"
    printf 'JAVA_HOME=%s\n' "$JAVA_HOME"
    javac -version
    ant -version
} 2>&1 | tee /dev/tty | clip.exe
```

### 5.4 JCC build mode

JCC 3.14 was installed from the JCC source bundled with the PyLucene 9.12.0 source archive. The build used non-shared mode because the installed JCC configuration did not support the requested `--shared` mode. The PyLucene Makefile was configured accordingly (`JCC=$(PYTHON) -m jcc`, not `--shared`).

The Makefile was configured to use the project's virtual environment Python and Python 3.11. The successful build compiled the Lucene Java components, generated the JCC wrapper and built/installed the `lucene-9.12.0` Python wheel.

The original source archive was downloaded from the Apache Lucene/PyLucene distribution site. Its recorded SHA-256 was:

`5d7223e87883e64ec0cd3e62a983a4bf50dce68c997081c8989e233b90cee115`

This hash was recorded locally; it was not independently verified against an official checksum in the setup notes.

### 5.5 PyLucene smoke test

The following test was successful after installation:

```python
import lucene

from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.document import Document, TextField
from org.apache.lucene.index import DirectoryReader, IndexWriter, IndexWriterConfig
from org.apache.lucene.queryparser.classic import QueryParser
from org.apache.lucene.search import IndexSearcher
from org.apache.lucene.store import ByteBuffersDirectory

lucene.initVM()

store = ByteBuffersDirectory()
analyzer = StandardAnalyzer()
config = IndexWriterConfig(analyzer)

writer = IndexWriter(store, config)
doc = Document()
doc.add(TextField("content", "Catan is a popular strategy board game.", TextField.Store.YES))
writer.addDocument(doc)
writer.close()

reader = DirectoryReader.open(store)
searcher = IndexSearcher(reader)
query = QueryParser("content", analyzer).parse("strategy")
hits = searcher.search(query, 10).scoreDocs

print("PyLucene version:", lucene.VERSION)
print("Matching documents:", len(hits))

reader.close()
store.close()
```

Expected result: PyLucene version `9.12.0` and one matching document. The actual project will need its own schema, analyzers, field mapping and query tests.

## 6. Data requirements

The selected BGG snapshot inspected on 20 November 2026 is `data/bgg_games/bgg_games_20261025_113653.tsv`. It contains 17,652 data rows and 43 columns, representing 17,648 distinct `app_id` values. Four IDs occur twice; each duplicate pair is identical across all columns. The controlled retrieval experiment should use one row per `app_id` (17,648 unique records) while preserving the original source TSV unchanged. See [the reproducibility audit](reproducibility_audit.md) for the dataset findings and duplicate IDs.

A Wikipedia dump is present locally at `data/wiki/enwiki-latest-pages-articles.xml.bz2`, but it is ignored by Git and its rolling `latest` filename does not identify a fixed release. No Wikipedia/Spark extraction and join implementation was found in the audited repository. Do not treat this local file as a reproducible project input yet. If it is used in a future pipeline, record its source, fixed release/date, download date and checksum.

Generated outputs such as Spark output directories and Lucene indexes should remain outside version control unless a small reproducible sample is intentionally committed. The 24 parser HTML fixtures under `testing/fixtures/` are intentionally version-controlled test inputs.

## 7. Reproducing the project in its current state

The repository contains several independently reproducible components, but not a complete end-to-end course pipeline. The current boundary is:

1. **Python setup:** create the Python 3.11 virtual environment and install the dependencies needed for the component being used. `requirements.txt` is the only dependency manifest, but it uses minimum versions and is not a complete lock of the native Spark/PyLucene toolchain.
2. **Parser tests:** install the test dependencies and run `python -m pytest testing/test_parsing.py` from the repository root. The tests use committed local HTML fixtures and do not require a live browser. A successful pytest run in a clean environment remains to be recorded.
3. **Dataset validation:** run `python -m experiments.testdata data/bgg_games/bgg_games_20261025_113653.tsv` to inspect the validator's supported arguments, then validate the selected TSV.
4. **BGG crawling:** install Playwright and tqdm. For uncached pages, start Chrome with remote debugging as described in `docs/startchrome.md`; the crawler connects to that external browser through CDP. Preserve both the TSV snapshot and crawl-state JSON when resuming a crawl. Cached HTML can avoid live requests for pages already captured.
5. **Custom Python indexer:** `src/indexers.py` provides the current natural-TF, classic-IDF and smoothed-IDF baseline. Its command-line handling and logging are currently coupled to module import, and its final experiment interface has not yet been designed.
6. **Spark:** the local Spark smoke test in this guide is reproducible in the recorded environment. The Wikipedia extraction, BGG join and report are not yet implemented in the audited repository.
7. **PyLucene:** the in-memory smoke test in this guide verifies the native installation. A project BGG index, schema and query workflows are not yet implemented.

Consequently, a fresh user can reproduce individual verified environment checks and can work with the existing BGG/parser/indexer code after installing its dependencies and supplying the required data. They cannot yet reproduce a complete BGG → Wikipedia/Spark → PyLucene → evaluation pipeline. See [the Phase 3.2 reproducibility audit](reproducibility_audit.md) for the detailed component-by-component findings and limitations.
