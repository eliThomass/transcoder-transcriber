import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime

from api.config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS uploads (
    id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    key TEXT NOT NULL,
    received INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    upload_id TEXT NOT NULL UNIQUE REFERENCES uploads(id),
    status TEXT NOT NULL,
    file_name TEXT NOT NULL,
    settings TEXT NOT NULL,
    transcribe INTEGER NOT NULL,
    input_key TEXT NOT NULL,
    output_key TEXT,
    transcript_key TEXT,
    output_size_bytes INTEGER,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


def utcnow() -> datetime:
    return datetime.now(UTC)


# Fixed-width ISO text so ORDER BY on timestamps sorts correctly.
def to_db(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="microseconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as conn, conn:
        conn.executescript(SCHEMA)
        # Jobs run in this process, so any left mid-run by a restart will never finish.
        conn.execute(
            "UPDATE jobs SET status = 'failed', error = 'Encoding was interrupted. Try again.' "
            "WHERE status IN ('queued', 'processing')"
        )


# FastAPI dependency: one connection per request.
def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
