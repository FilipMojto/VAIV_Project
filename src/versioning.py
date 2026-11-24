from datetime import datetime
from pathlib import Path

from src.config import DATA_DIR


class SmartVersioner:
    """Manages file versioning smartly.
    It finds all files in the provided directory that match the following pattern:

    - Starts with the provided filename
    - Ends with the provided extension

    """

    def __init__(
        self, stem: str, data_dir: Path = DATA_DIR, extension: str = ".txt"
    ):
        self.data_dir = data_dir
        self.base_filename = stem
        self.extension = extension if extension.startswith(".") else f".{extension}"
        self._temp_file = self.data_dir / f"{self.base_filename}_temp{self.extension}"
        self._temp_file.parent.mkdir(parents=True, exist_ok=True)

    def get_latest_match(self):
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

        latest_file = self.get_latest_match()

        if latest_file:
            print(f"--- CHECKPOINT FOUND: {latest_file.name} ---")
            return open(latest_file, "r", encoding="utf-8")

        return None

    def get_next_save_file(self) -> Path:
        """Generates the next timestamped filename for saving."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.base_filename}_{timestamp}{self.extension}"
        final_file = self.data_dir / filename
        suffix = 1

        # to prevent overwriting if multiple scripts are launched at the same time (race condition)
        # example file: bgg_games_20261015_143022_000001.tsv. ...
        while final_file.exists():
            filename = f"{self.base_filename}_{timestamp}_{suffix:06d}{self.extension}"
            final_file = self.data_dir / filename
            suffix += 1

        return final_file

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
