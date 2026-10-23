import csv
from datetime import datetime
from pathlib import Path

from src.config import DATA_DIR


class SmartVersioner:
    """Manages file versioning smartly.
    It finds all files in the provided dictionary that match the following pattern:
    
    - Starts with the provided filename
    - Ends with the provided extension.
    .

    """

    def __init__(
        self, base_filename: str, data_dir: Path = DATA_DIR, extension: str = ".txt"
    ):
        self.data_dir = data_dir
        self.base_filename = base_filename
        self.extension = extension if extension.startswith(".") else f".{extension}"
        self._temp_file = self.data_dir / f"{self.base_filename}_temp{self.extension}"

    def get_latest_file(self):
        # glob finds all files matching the pattern, and sorted() puts the newest timestamp last
        files = [
            file
            for file in self.data_dir.glob(f"{self.base_filename}_*{self.extension}")
            if file != self._temp_file
        ]
        if not files:
            return None

        return sorted(files)[-1]
    
    def open_latest_save_file(self):
        """Finds the most recent timestamped file in DATA_DIR."""
  
        latest_file = self.get_latest_file()

        if latest_file:
            print(f"--- CHECKPOINT FOUND: {latest_file.name} ---")
            return open(latest_file, "r", encoding="utf-8")

        return None
        # return sorted(files)[-1]

    def get_next_save_file(self):
        """Generates the next timestamped filename for saving."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.base_filename}_{timestamp}{self.extension}"
        final_file = self.data_dir / filename
        suffix = 1
        while final_file.exists():
            filename = (
                f"{self.base_filename}_{timestamp}_{suffix:06d}{self.extension}"
            )
            final_file = self.data_dir / filename
            suffix += 1
        return final_file

    def open_temp(self, newline: str = "\n"):
        """Opens the temporary file for writing."""
        self._temp_file.parent.mkdir(parents=True, exist_ok=True)
        self._temp_file_handle = open(self._temp_file, "w", newline=newline, encoding="utf-8")
        return self._temp_file_handle

    def dump_temp_to_final(self):
        """Renames the temporary file to a final timestamped file."""
        if hasattr(self, "_temp_file_handle") and self._temp_file_handle:
            try:
                self._temp_file_handle.close()
            except Exception:
                pass
            
        if self._temp_file.exists():
            final_file = self.get_next_save_file()
            self._temp_file.rename(final_file)
            print(f"Temporary file renamed to: {final_file.name}")

    # -----------------------------------------------------------------------------
    # getters & setters
    # -----------------------------------------------------------------------------
    
    def get_temp_file_path(self):
        return self._temp_file

    # def append_existing_ids(
    #     self,
    #     collected_ids: dict,
    #     target_count: int = None,
    #     delimiter: str = "\t",
    #     id_column_index: int = 0,
    # ):
    #     """
    #     Appends existing IDs from the latest checkpoint file to the collected_ids dictionary.

    #     Args:
    #         versioner (SmartVersioner): The versioning utility to manage checkpoint files.
    #         collected_ids (dict): The dictionary to store collected IDs.
    #     """
    #     latest_file = self.open_latest_save_file()

    #     if latest_file:
    #         with latest_file as f:
    #             for line in f:
    #                 columns = line.strip().split(delimiter)
    #                 if not line.strip() or len(columns) <= id_column_index:
    #                     continue
    #                 app_id = columns[id_column_index]
    #                 if app_id:
    #                     collected_ids[app_id] = None  # Dict keys act as an ordered set
    #         print(f"Loaded {len(collected_ids)} existing IDs into memory.")

    #         if target_count is not None and len(collected_ids) >= target_count:
    #             print("Target already reached in the checkpoint file! Exiting.")
    #             return

    # def append_existing_tsv_rows(self, writer: csv.DictWriter, collected_ids: dict, id_column: str = "app_id"):
    #     """Copies the latest TSV checkpoint into ``writer`` and records its app IDs."""
    #     latest_file = self.open_latest_save_file()
    #     if not latest_file:
    #         return

    #     with latest_file as tsv_file:
    #         reader = csv.DictReader(tsv_file, delimiter="\t")
    #         for row in reader:
    #             app_id = (row.get(id_column) or "").strip()
    #             if not app_id or app_id in collected_ids:
    #                 continue
    #             writer.writerow(row)
    #             collected_ids[app_id] = None

    #     print(
    #         f"Copied {len(collected_ids)} existing scraped games into the new checkpoint."
    #     )
