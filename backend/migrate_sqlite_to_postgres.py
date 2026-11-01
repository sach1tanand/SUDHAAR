"""Copy an existing Sudhaar SQLite database into an empty PostgreSQL database.

Set DATABASE_URL and optionally SUDHAAR_SQLITE_PATH, then run:
    python -m backend.migrate_sqlite_to_postgres

The source SQLite file is opened read-only and is never modified or removed. The
PostgreSQL copy is one transaction; a failure rolls the copy back. Existing target
tables may be empty (for example, created by app startup), but must contain no rows.
"""
import os
import sqlite3
import sys

from . import db
from .config import DATABASE_URL, DB_PATH

TABLES = (
    "users", "otps", "departments", "officers", "field_officers", "zones",
    "complaints", "media", "timeline", "notifications", "audit", "ai_trace",
)

def main():
    if not DATABASE_URL:
        raise SystemExit("Set DATABASE_URL to the destination PostgreSQL connection string first.")
    source = os.environ.get("SUDHAAR_SQLITE_PATH", str(DB_PATH))
    if not os.path.isfile(source):
        raise SystemExit(f"SQLite source database does not exist: {source}")

    db.init()
    src = sqlite3.connect(f"file:{os.path.abspath(source)}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    try:
        with db.conn() as dst:
            for table in TABLES:
                if dst.execute(f'SELECT COUNT(*) AS n FROM "{table}"').fetchone()["n"]:
                    raise SystemExit(f"Destination table {table} is not empty; refusing to merge or overwrite data.")
            for table in TABLES:
                rows = src.execute(f'SELECT * FROM "{table}"').fetchall()
                if not rows:
                    continue
                cols = rows[0].keys()
                names = ",".join(f'"{name}"' for name in cols)
                marks = ",".join(["%s"] * len(cols))
                sql = f'INSERT INTO "{table}" ({names}) VALUES ({marks})'
                dst.executemany(sql, [tuple(row) for row in rows])
            for table in TABLES:
                seq = dst.execute("SELECT pg_get_serial_sequence(%s, 'id') AS seq", (table,)).fetchone()["seq"]
                if seq:
                    max_id = dst.execute(f'SELECT COALESCE(MAX(id),0) AS n FROM "{table}"').fetchone()["n"]
                    dst.execute("SELECT setval(%s, %s, %s)", (seq, max(max_id, 1), max_id > 0))
        print(f"Copied SQLite data from {source} to PostgreSQL. Source file was left unchanged.")
    finally:
        src.close()

if __name__ == "__main__":
    main()
