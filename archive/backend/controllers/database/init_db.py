#!/usr/bin/env python3
"""
init_db.py  --sql <sql_dir_or_file>  --db <db_path>

Initializes a SQLite database from a directory of ordered .sql files
(or a single .sql file).  Called by DatabaseConnection (C++/Qt) on first run.

Usage:
    python init_db.py --sql /path/to/backend/sql --db /path/to/device_network.db
"""

import argparse
import os
import sqlite3
import sys


def collect_sql_files(sql_path: str) -> list:
    """Return sorted list of absolute .sql file paths to execute.

    When *sql_path* is a directory, all *.sql files are executed in
    alphabetical order (which equals numeric order given the NN_ prefix
    naming convention).  main.sql is intentionally skipped because it
    relies on the SQLite CLI ``.read`` directive that Python cannot
    execute.
    """
    if os.path.isdir(sql_path):
        files = sorted(
            f for f in os.listdir(sql_path)
            if f.endswith(".sql") and f != "main.sql"
        )
        if not files:
            raise ValueError(f"No .sql files found in directory: {sql_path}")
        return [os.path.join(sql_path, f) for f in files]
    elif os.path.isfile(sql_path):
        return [sql_path]
    else:
        raise FileNotFoundError(f"SQL path not found: {sql_path}")


def init_db(sql_path: str, db_path: str) -> None:
    sql_files = collect_sql_files(sql_path)

    # Ensure the target directory exists.
    db_dir = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    # Enable foreign-key enforcement for the bootstrap connection.
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        for sql_file in sql_files:
            print(f"[init_db] Executing: {os.path.basename(sql_file)}")
            with open(sql_file, encoding="utf-8") as fh:
                sql = fh.read()
            # executescript() commits any pending transaction before running,
            # handles multiple statements, and is safe for DDL-heavy files.
            conn.executescript(sql)

        conn.commit()
        print(f"[init_db] Database initialized successfully at: {db_path}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize a SQLite database from ordered .sql files."
    )
    parser.add_argument(
        "--sql",
        required=True,
        help="Path to a directory of .sql files or a single .sql file",
    )
    parser.add_argument(
        "--db",
        required=True,
        help="Path to the SQLite database file to create",
    )
    args = parser.parse_args()

    try:
        init_db(args.sql, args.db)
    except Exception as exc:
        print(f"[init_db] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
