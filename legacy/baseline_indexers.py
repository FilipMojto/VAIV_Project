from argparse import ArgumentParser
from collections import Counter, defaultdict
import csv
import json
import math
import logging
from pathlib import Path
import re

from src.config import BGG_GAMES_DIR, LOG_DIR

LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file_path = LOG_DIR / "indexer_search.log"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

from src.versioning import SmartVersioner


class BGGIndexer:

  def __init__(self, tsv_path: Path):
    self.tsv_path = tsv_path
    self.documents = {}  # doc_id -> metadata/text
    self.doc_count = 0
    self.inverted_index = defaultdict(set)  # term -> set(doc_ids)
    self.term_freqs = defaultdict(Counter)  # doc_id -> Counter(term: frekvencia)

  def build_index(self):
    """Načíta TSV súbor, tokenizuje text a vytvorí inverzný index a TF."""
    if not self.tsv_path.exists():
      raise FileNotFoundError(f"TSV file not found: {self.tsv_path}")

    logging.info("Načítavam TSV súbor a spúšťam indexáciu z: %s", self.tsv_path)

    with open(self.tsv_path, mode="r", encoding="utf-8") as file:
      reader = csv.DictReader(file, delimiter="\t")

      for row in reader:
        doc_id = row.get("app_id")
        if not doc_id:
          continue

        text_fields = [
            row.get("game_title", ""),
            row.get("alternate_names", ""),
            row.get("short_description", ""),
            row.get("description", ""),
            row.get("game_type", ""),
            row.get("game_category", ""),
            row.get("game_mechanic", ""),
            row.get("game_family", ""),
            row.get("designer", ""),
            row.get("publisher", ""),
            row.get("awards_honors", ""),
        ]
        combined_text = " ".join(text_fields)
        tokens = self._tokenize(combined_text)

        self.documents[doc_id] = row
        self.doc_count += 1

        term_counts = Counter(tokens)
        self.term_freqs[doc_id] = term_counts

        for term in term_counts:
          self.inverted_index[term].add(doc_id)

    logging.info(
        "Index úspešne vytvorený. Celkovo indexovaných dokumentov: %d,"
        " unikátnych termínov: %d",
        self.doc_count,
        len(self.inverted_index),
    )

  def _tokenize(self, text: str) -> list[str]:
    return re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

  def compute_idf_classic(self, term: str) -> float:
    df = len(self.inverted_index.get(term, set()))
    if df == 0:
      return 0.0
    return math.log(self.doc_count / df)

  def compute_idf_smooth(self, term: str) -> float:
    df = len(self.inverted_index.get(term, set()))
    return math.log((self.doc_count + 1) / (df + 1)) + 1.0

  def search(self, query: str, idf_method: str = "classic") -> list[tuple]:
    query_terms = self._tokenize(query)
    scores = defaultdict(float)

    idf_func = (
        self.compute_idf_classic
        if idf_method == "classic"
        else self.compute_idf_smooth
    )

    for term in query_terms:
      idf = idf_func(term)
      matching_docs = self.inverted_index.get(term, set())

      for doc_id in matching_docs:
        tf = self.term_freqs[doc_id][term]
        scores[doc_id] += tf * idf

    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


# --- Konfigurácia príkazového riadku ---
parser = ArgumentParser(
    description=(
        "BGG Indexer & Search Engine - Consultation 3 evaluation script."
    )
)
parser.add_argument(
    "--query",
    type=str,
    nargs="+",
    default=[
        "deck building card game",
        "cooperative strategy game",
        "dice rolling family game",
    ],
    help=(
        "Zadaj jeden alebo viac dopytov (queries) oddelených medzerou, napr."
        " --query 'deck building' 'strategy'"
    ),
)
args = parser.parse_args()


if __name__ == "__main__":
  tsv_versioner = SmartVersioner(
      stem="bgg_games", data_dir=BGG_GAMES_DIR, extension=".tsv"
  )

  indexer = BGGIndexer(tsv_path=tsv_versioner.get_latest_match())
  indexer.build_index()

  logging.info("=== SPUSTENIE VYHĽADÁVANIA PRE WIKI POROVNANIE ===")

  for query in args.query:
    logging.info("--- Hľadaný dopyt: '%s' ---", query)

    # 1. Klasické IDF
    results_classic = indexer.search(query, idf_method="classic")
    classic_output = []
    for doc_id, score in results_classic[:3]:
      title = indexer.documents[doc_id].get("game_title", "Neznáme")
      doc_row = indexer.documents[doc_id]
      classic_output.append({
          "app_id": doc_id,
          "title": doc_row.get("game_title", "Neznáme"),
          "designer": doc_row.get("designer", "Neznámy"),
          "publisher": doc_row.get("publisher", "Neznámy"),
          "score": round(score, 2),
      })

    # 2. Smooth IDF
    results_smooth = indexer.search(query, idf_method="smooth")
    smooth_output = []
    for doc_id, score in results_smooth[:3]:
      title = indexer.documents[doc_id].get("game_title", "Neznáme")
      # smooth_output.append({"app_id": doc_id, "title": title, "score": round(score, 2)})
      doc_row = indexer.documents[doc_id]
      smooth_output.append({
          "app_id": doc_id,
          "title": doc_row.get("game_title", "Neznáme"),
          "designer": doc_row.get("designer", "Neznámy"),
          "publisher": doc_row.get("publisher", "Neznámy"),
          "score": round(score, 2),
      })

    # Zalogovanie do konzoly aj do JSON/logu
    search_summary = {
        "query": query,
        "classic_idf_top3": classic_output,
        "smooth_idf_top3": smooth_output,
    }

    logging.info("Výsledky (JSON):\n%s", json.dumps(search_summary, indent=4, ensure_ascii=False))

  logging.info("=== Všetky dopyty úspešne spracované. Logy uložené v: %s ===", log_file_path)