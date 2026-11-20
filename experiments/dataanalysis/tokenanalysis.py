from pathlib import Path
import csv
import tiktoken

from src.config import BGG_DIR, BGG_FILE_EXTENSION, BGG_FILE_STEM, HTML_DIR
from src.versioning import SmartVersioner


def count_dataset_tokens_pure_python():
    # Inicializácia tiktoken enkódera
    enc = tiktoken.get_encoding("cl100k_base")

    print("=" * 60)
    print("SPÚŠŤAM VÝPOČET TOKENOV (Čistý Python - bez Pandas)")
    print("=" * 60)

    # ==========================================
    # 1. VÝPOČET PRE VŠETKY LOKÁLNE HTML SÚBORY
    # ==========================================
    html_dir = HTML_DIR  # Uprav cestu, ak treba
    total_html_tokens = 0
    html_file_count = 0

    if html_dir.exists():
        for html_file in html_dir.glob("*.html"):
            try:
                content = html_file.read_text(encoding="utf-8", errors="ignore")
                tokens = len(enc.encode(content))
                total_html_tokens += tokens
                html_file_count += 1
            except Exception as e:
                print(f"Chyba pri čítaní {html_file.name}: {e}")

        print(f"[HTML CACHE]")
        print(f"  - Počet spracovaných HTML súborov: {html_file_count:,}")
        print(f"  - Celkový objem surového HTML: {total_html_tokens:,} tokenov\n")
    else:
        print(f"[HTML CACHE] Priečinok '{html_dir}' nebol nájdený.\n")

    # ==========================================
    # 2. VÝPOČET PRE TEXTOVÉ ATRIBÚTY V TSV
    # ==========================================
    #   tsv_path = Path("data/game_metadata.tsv")  # Uprav cestu k najnovšiemu TSV
    tsv_versioner = SmartVersioner(stem=BGG_FILE_STEM, data_dir=BGG_DIR, extension=BGG_FILE_EXTENSION)
    tsv_path = tsv_versioner.get_latest_match()
    relevant_text_fields = [
        "game_title",
        "alternate_names",
        "short_description",
        "description",
        "game_type",
        "game_category",
        "game_mechanic",
        "game_family",
        "designer",
        "artist",
        "publisher",
        "awards_honors",
        "reimplements",
        "reimplemented_by",
        "integrates_with",
        "contains",
        "contained_in",
    ]

    if tsv_path.exists():
        total_tsv_text_tokens = 0
        field_stats = {field: 0 for field in relevant_text_fields}

        try:
            with open(tsv_path, mode="r", encoding="utf-8", errors="ignore") as file:
                reader = csv.DictReader(file, delimiter="\t")
                row_count = 0
                for row in reader:
                    row_count += 1
                for field in relevant_text_fields:
                    if field in row and row[field]:
                        val = str(row[field])
                        t_count = len(enc.encode(val))
                        field_stats[field] += t_count
                        total_tsv_text_tokens += t_count

            print(f"[TSV METADÁTA - Súbor: {tsv_path.name}]")
            print(f"  - Spracovaných riadkov (hier): {row_count:,}")
            print(
                f"  - Celkový objem textových atribútov:"
                f" {total_tsv_text_tokens:,} tokenov"
            )       
            print("  - Detail podľa atribútov:")
            
            for field, count in field_stats.items():
                print(f"      * {field}: {count:,} tokenov")
        except Exception as e:
            print(f"Chyba pri čítaní TSV: {e}")
    else:
        print(f"[TSV METADÁTA] Súbor sa nenašiel na ceste: {tsv_path}")

    print("=" * 60)


if __name__ == "__main__":
    count_dataset_tokens_pure_python()