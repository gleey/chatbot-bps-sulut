"""
SQLite database untuk session persistence.
Tabel: sessions (data user), messages (conversation history).
ponytail: kalau multi-worker Flask, ganti ke Redis; 1 worker cukup SQLite.
"""
import sqlite3
import os

DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "chatbot.db"))

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    phone       TEXT PRIMARY KEY,
    tujuan      TEXT DEFAULT '',
    step        TEXT DEFAULT 'awal',
    last_active REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL,
    role  TEXT NOT NULL,
    text  TEXT NOT NULL,
    ts    REAL DEFAULT 0,
    FOREIGN KEY (phone) REFERENCES sessions(phone) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS bps_cache (
    cache_key TEXT PRIMARY KEY,
    response  TEXT NOT NULL,
    ts        REAL NOT NULL
);
"""

_initialized = False


def get_conn():
    """Satu koneksi per panggilan — aman untuk single-thread Flask."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Buat tabel jika belum ada. Idempotent — aman dipanggil berkali-kali."""
    global _initialized
    if _initialized:
        return
    conn = get_conn()
    try:
        conn.executescript(_CREATE_SQL)
        conn.commit()
    finally:
        conn.close()
    _initialized = True


def reset_db():
    """Hapus semua data. Untuk keperluan testing/reset total."""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM bps_cache")
        conn.commit()
    finally:
        conn.close()
