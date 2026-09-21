

from src.versioning import SmartVersioner


def append_existing_ids(versioner: SmartVersioner, collected_ids: dict, target_count: int = None):
    """
    Appends existing IDs from the latest checkpoint file to the collected_ids dictionary.
    
    Args:
        versioner (SmartVersioner): The versioning utility to manage checkpoint files.
        collected_ids (dict): The dictionary to store collected IDs.
    """
    latest_file = versioner.open_latest_save_file()
    
    if latest_file:
        with latest_file as f:
            for line in f:
                app_id = line.strip()
                if app_id:
                    collected_ids[app_id] = None  # Dict keys act as an ordered set
        print(f"Loaded {len(collected_ids)} existing IDs into memory.")

        if target_count is not None and len(collected_ids) >= target_count:
            print("Target already reached in the checkpoint file! Exiting.")
            return