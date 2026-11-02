"""SQLite snapshots and recovery into new files; existing files are never replaced."""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

from config import database_path


def snapshot(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise ValueError("Source database does not exist.")
    if destination == database_path() or destination == source:
        raise ValueError("Choose a new destination, separate from the operational database.")
    with closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)) as src:
        if src.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Source database failed its integrity check.")
        if src.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Source database contains broken foreign keys.")
        with destination.open("xb"):
            pass
        with closing(sqlite3.connect(destination)) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Snapshot failed verification; do not use it for recovery.")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "recover"))
    parser.add_argument("destination", type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.action == "recover" and args.source is None:
        parser.error("Recovery requires an explicit --source backup file.")
    try:
        print(snapshot(args.source or database_path(), args.destination))
    except (OSError, ValueError, sqlite3.Error):
        parser.exit(
            1,
            "Snapshot failed. Verify paths, permissions and database integrity; existing files were not replaced.\n",
        )


if __name__ == "__main__":
    main()
