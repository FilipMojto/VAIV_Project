import csv
from pathlib import Path

from src.config import BGG_GAMES_DIR
from src.versioning import SmartVersioner


class FileCache:
    def __init__(
        self,
        file_path: Path,
        identifier_pos: int = 1,
        delimiter: str = "\t",
        contains_header: bool = True,
    ):
        if identifier_pos < 1:
            raise ValueError("identifier_pos must be a 1-based column position")

        if not file_path.exists():
            raise FileNotFoundError(f"Cache file does not exist: {file_path}")

        self.row_ids: set[str] = set()
        with file_path.open(mode="r", encoding="utf-8", newline="") as file:
            reader = csv.reader(file, delimiter=delimiter)

            if contains_header:
                next(reader, None)

            for row_number, row in enumerate(
                reader, start=2 if contains_header else 1
            ):
                if not row:
                    continue
                if len(row) < identifier_pos:
                    raise ValueError(
                        f"Cache row {row_number} has no column {identifier_pos}"
                    )
                identifier = row[identifier_pos - 1].strip()
                if identifier:
                    self.row_ids.add(identifier)

        print(f"Found {len(self.row_ids)} in file!")

    def contains(self, identifier: str) -> bool:
        return identifier in self.row_ids


if __name__ == "__main__":
    file_versioner = SmartVersioner(
        base_filename="bgg_games", data_dir=BGG_GAMES_DIR, extension=".tsv"
    )
    file_path = file_versioner.get_latest_file()

    if file_path is None:
        print("No cache file found.")
    else:
        cache = FileCache(file_path=file_path, identifier_pos=1, delimiter="\t")
        print(cache.row_ids)
