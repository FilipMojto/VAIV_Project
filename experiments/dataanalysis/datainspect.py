import pandas as pd

from src.config import BGG_GAMES_DIR
from src.versioning import SmartVersioner

if __name__ == "__main__":
    file_versioner = SmartVersioner(
        stem="bgg_games", data_dir=BGG_GAMES_DIR, extension=".tsv"
    )

    tsv_path = file_versioner.get_latest_match()

    if tsv_path == None:
        raise FileNotFoundError("No version of the file was found in the provided directory.")
    problematic_id = 35
    df = pd.read_csv(tsv_path, sep="\t", dtype=str)
    game_row = df.iloc[problematic_id]
    
    if not game_row.empty:
        print(f"\n--- Detail hry ID {problematic_id} ---")
        # Transpose (.T) nám vypíše stĺpce pod seba, čo sa oveľa lepšie číta
        print(game_row.T)
    else:
        print(f"Hra s ID {problematic_id} sa v TSV nenachádza.")

    df_filtered = df[df["game_title"] == "7 Wonders Duel"]
    print(df_filtered['play_time_max'])