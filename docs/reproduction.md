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

The project uses BGG records in TSV format. During development, the dataset was described as approximately 17,652 records and 42 fields. Confirm the final file's row count and schema before using those figures in a report.

The project also requires a Wikipedia XML dump in `.xml.bz2` format for the planned Spark enrichment phase. The dump is a large external input and should not be committed to Git. Document its source, download date/version, checksum and exact path when the pipeline is finalized.

Generated outputs such as Spark output directories and Lucene indexes should also remain outside version control unless a small reproducible sample is intentionally committed.

## 7. Reproducing the project itself

A complete end-to-end reproduction guide still depends on finalizing the entry points and configuration for each pipeline stage. At minimum, a fresh user will need to:

1. clone the repository;
2. create the supported Python environment;
3. install the declared project dependencies;
4. build/install PyLucene using the compatible Java/JCC toolchain if Lucene tasks are required;
5. obtain the BGG TSV dataset and the documented Wikipedia dump;
6. run the BGG/custom-indexer stage;
7. run the Spark extraction and join stage;
8. build the Lucene index and run the required query types;
9. run the evaluation scripts using the documented query set and relevance judgments.

The exact commands for steps 5–9 should be added after the relevant project entry points and output paths are finalized. They are intentionally not invented in this document.
