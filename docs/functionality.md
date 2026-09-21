# File Versioning and Safe Writes

Instead of blindly overwriting files, make the script strictly non-destructive.

## Atomic Writes (Temporary File Strategy)

Write the results to `app_ids_temp.txt` instead of directly to `app_ids.txt`. Rename the temporary file to `app_ids.txt` only after the entire 15,000-game scrape completes successfully. If the script crashes halfway through, the original file remains untouched.

## Timestamped Versioning

Generate a new file for every run using the exact timestamp, such as `app_ids_2026-09-20_10-45.txt`. This preserves a history of scrapes and prevents accidental overwrites.

## Smart Appending (Checkpointing)

If `app_ids.txt` exists, read its IDs into memory, skip completed pages, and open the file in append mode (`"a"`). This allows a 15,000-game scrape to be paused and resumed over several days without losing progress.

# Automated Backup Strategies

Beyond versioning, add a safety net in case the main working directory becomes corrupted.

## Local Snapshotting Before Execution

When the script starts, check whether `app_ids.txt` exists. If it does, use Python's `shutil` module to copy it to `./data/backups/` with a timestamp before beginning a new scrape.

## Cloud or External Syncing

For 15,000 rows, the resulting files are only a few megabytes. You can version-control the `./data` directory with Git or automatically upload the `.tsv` and `.txt` files to a cloud service, such as an AWS S3 bucket or Google Drive, after each successful run.