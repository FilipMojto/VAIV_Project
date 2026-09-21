


from datetime import datetime
from pathlib import Path

from src.config import DATA_DIR


class SmartVersioner:

    def __init__(self, base_filename: str, data_dir: Path = DATA_DIR, extension: str = ".txt"):
        self.data_dir = data_dir
        self.base_filename = base_filename
        self.extension = extension if extension.startswith(".") else f".{extension}"
        self.temp_file = self.data_dir / f"{self.base_filename}_temp{self.extension}"

    def open_latest_save_file(self):
        """Finds the most recent timestamped file in DATA_DIR."""
        # glob finds all files matching the pattern, and sorted() puts the newest timestamp last
        files = [
            file for file in self.data_dir.glob(f"{self.base_filename}_*{self.extension}")
            if file != self.temp_file
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

    def write_to_temp(self, data: list):
        """Writes data to a temporary file."""
        # if self.write_to_temp_file:
        with open(self.temp_file, "w", encoding="utf-8") as f:
            for item in data:
                f.write(f"{item}\n")
        print(f"Data written to temporary file: {self.temp_file.name}")

    def dump_temp_to_final(self):
        """Renames the temporary file to a final timestamped file."""
        if self.temp_file.exists():
            final_file = self.get_next_save_file()
            self.temp_file.rename(final_file)
            print(f"Temporary file renamed to: {final_file.name}")
