


import csv
from datetime import datetime
from pathlib import Path

from src.config import DATA_DIR


class SmartVersioner:

    def __init__(self, base_filename: str, data_dir: Path = DATA_DIR, extension: str = ".txt"):
        self.data_dir = data_dir
        self.base_filename = base_filename
        self.extension = extension if extension.startswith(".") else f".{extension}"
        self._temp_file = self.data_dir / f"{self.base_filename}_temp{self.extension}"

    def open_latest_save_file(self):
        """Finds the most recent timestamped file in DATA_DIR."""
        # glob finds all files matching the pattern, and sorted() puts the newest timestamp last
        files = [
            file for file in self.data_dir.glob(f"{self.base_filename}_*{self.extension}")
            if file != self._temp_file
        ]
        if not files:
            return None

        latest_file = sorted(files)[-1]

        if latest_file:
            print(f"--- CHECKPOINT FOUND: {latest_file.name} ---")
            return open(latest_file, "r", encoding="utf-8")

        return None
        # return sorted(files)[-1]

    def get_next_save_file(self):
        """Generates the next timestamped filename for saving."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.data_dir / f"{self.base_filename}_{timestamp}{self.extension}"

    def write_to_temp(self, newline: str = "\n"):
        """Opens the temporary file for writing."""
        self._temp_file.parent.mkdir(parents=True, exist_ok=True)
        return open(self._temp_file, "w", newline=newline, encoding="utf-8")


    def dump_temp_to_final(self):
        """Renames the temporary file to a final timestamped file."""
        if self._temp_file.exists():
            final_file = self.get_next_save_file()
            self._temp_file.rename(final_file)
            print(f"Temporary file renamed to: {final_file.name}")

    def append_existing_ids(self, collected_ids: dict, target_count: int = None,
                        delimiter: str = "\t", id_column_index: int = 0):
        """
        Appends existing IDs from the latest checkpoint file to the collected_ids dictionary.
        
        Args:
            versioner (SmartVersioner): The versioning utility to manage checkpoint files.
            collected_ids (dict): The dictionary to store collected IDs.
        """
        latest_file = self.open_latest_save_file()
        
        if latest_file:
            with latest_file as f:
                for line in f:
                    columns = line.strip().split(delimiter)
                    if not line.strip() or len(columns) <= id_column_index:
                        continue
                    app_id = columns[id_column_index]
                    if app_id:
                        collected_ids[app_id] = None  # Dict keys act as an ordered set
            print(f"Loaded {len(collected_ids)} existing IDs into memory.")

            if target_count is not None and len(collected_ids) >= target_count:
                print("Target already reached in the checkpoint file! Exiting.")
                return


    def append_existing_tsv_rows(self, writer: csv.DictWriter, collected_ids: dict):
        """Copies the latest TSV checkpoint into ``writer`` and records its app IDs."""
        latest_file = self.open_latest_save_file()
        if not latest_file:
            return

        with latest_file as tsv_file:
            reader = csv.DictReader(tsv_file, delimiter="\t")
            for row in reader:
                app_id = (row.get("app_id") or "").strip()
                if not app_id or app_id in collected_ids:
                    continue
                writer.writerow(row)
                collected_ids[app_id] = None

        print(f"Copied {len(collected_ids)} existing scraped games into the new checkpoint.")

