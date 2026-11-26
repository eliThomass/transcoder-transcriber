import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime

from api.config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,  -- Cognito `sub`
    email TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id_hash TEXT PRIMARY KEY,  -- SHA-256 of the cookie value, never the value itself
    user_id TEXT NOT NULL REFERENCES users(id),
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS uploads (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    file_name TEXT NOT NULL,
    key TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
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


# Current time in UTC.
def utcnow() -> datetime:
    return datetime.now(UTC)


# Fixed-width ISO text so ORDER BY on timestamps sorts correctly.
def to_db(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="microseconds")


# Opens the SQLite database; rows can be read by column name.
def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# Creates the tables, and adds the owner column to databases made before accounts existed.
def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as conn, conn:
        conn.executescript(SCHEMA)
        for table in ("uploads", "jobs"):  # fixed names, not user input
            if "user_id" not in {col["name"] for col in conn.execute(f"PRAGMA table_info({table})")}:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT")  # old rows stay ownerless and hidden


# FastAPI dependency: one connection per request.
def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
