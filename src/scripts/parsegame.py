from argparse import ArgumentParser
import json
import logging
from pathlib import Path

from src.config import HTML_DIR, LOG_DIR
from src.parsing import GROUP_FIELD_MAPPINGS, ParserGroup, parse_general_fields, parse_html_metadata

# Nastavenie loggingu do súboru aj do konzoly
# LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file_path = LOG_DIR / "wiki_extraction.log"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            log_file_path, encoding="utf-8"
        ),  # Ukladá sa do súboru
        logging.StreamHandler(),  # Vypisuje sa aj do konzoly
    ],
)

parser = ArgumentParser(
    description=(
        "Helpful script for Consultation 3 realization purposes."
        " Displays and logs parsed metadata for specific games."
    )
)
parser.add_argument(
    "--id",
    type=int,
    nargs="+",
    required=True,
    help="Provide one or more IDs of games you want to process (e.g., --id 13"
    " 822).",
)
args = parser.parse_args()

if __name__ == "__main__":
  logging.info(
      "=== Spúšťam dávkové generovanie ukážok pre wiki (ID: %s) ===", args.id
  )

  for sample_app_id in args.id:
    html_file_path = HTML_DIR / f"{sample_app_id}.html"

    if html_file_path.exists():
        html_content = html_file_path.read_text(encoding="utf-8")

        # 1. Získaj parsovaný slovník
        parsed_data = parse_html_metadata(
            page_id=int(sample_app_id), html_content=html_content
        )

        logging.info("--- ZPRACOVANÁ HRA ID: %s ---", sample_app_id)
        logging.info(
            "PARSED DATA (JSON):\n%s",
            json.dumps(parsed_data, indent=4, ensure_ascii=False),
        )
        data, snippets = parse_general_fields(html_content=html_content, return_snippets=True)

        log_output = ""
        for field in GROUP_FIELD_MAPPINGS[ParserGroup.GENERAL_FIELDS]:
           log_output += f"{field}: {snippets.get(field)}"

        logging.info(
          "HTML SNIPPET (UKÁZKA VSTUPU):\n%s",
          log_output
        #   snippets.get('game_title')

        #   html_content[:600] + "\n... [skrátené pre wiki] ...",
      )
    else:
        logging.warning(
            "Hra s ID %s nie je v lokálnej cache (HTML súbor neexistuje).",
            sample_app_id,
        )

logging.info(
    "=== Generovanie úspešne dokončené. Logy nájdete v: %s ===",
    log_file_path,
)