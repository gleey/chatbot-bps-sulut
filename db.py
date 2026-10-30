"""
SQLite database untuk session persistence.
Tabel: sessions (data user), messages (conversation history).
ponytail: kalau multi-worker Flask, ganti ke Redis; 1 worker cukup SQLite.
"""
import sqlite3
import os
import threading
import time
from contextlib import closing

import config  # Load configuration before resolving DATABASE_PATH.

DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "chatbot.db"))
if not DB_PATH.strip() or DB_PATH == ":memory:" or "://" in DB_PATH:
    raise ValueError("DATABASE_PATH harus berupa path file SQLite persisten")

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

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL,
    started_at REAL NOT NULL,
    closed_at REAL,
    kind TEXT NOT NULL DEFAULT 'konsultasi',
    close_reason TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS webhook_inbox (
    event_id TEXT PRIMARY KEY,
    phone TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    reply TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS inbox_status ON webhook_inbox(status, created_at);
"""

_initialized = False
_init_lock = threading.Lock()


def get_conn():
    """Satu koneksi per panggilan — aman untuk single-thread Flask."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    try:
        descriptor = os.open(DB_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
    except FileExistsError:
        pass
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Buat tabel jika belum ada. Idempotent — aman dipanggil berkali-kali."""
    global _initialized
    with _init_lock:
        if _initialized:
            return
        conn = get_conn()
        try:
            existing = conn.execute("PRAGMA table_info(sessions)").fetchall()
            legacy = bool(existing) and "conversation_id" not in {r["name"] for r in existing}
            if legacy:
                backup_path = f"{DB_PATH}.pre-v2-{time.time_ns()}.bak"
                descriptor = os.open(backup_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(descriptor)
                with closing(sqlite3.connect(backup_path)) as backup:
                    conn.backup(backup)
                os.chmod(backup_path, 0o600)
            conn.executescript(_CREATE_SQL)
            conn.execute("BEGIN IMMEDIATE")
            if not existing or legacy:
                conn.execute("ALTER TABLE sessions ADD COLUMN conversation_id INTEGER")
                conn.execute("ALTER TABLE messages ADD COLUMN conversation_id INTEGER")
                for row in conn.execute("SELECT phone, last_active, step FROM sessions").fetchall():
                    cursor = conn.execute(
                        "INSERT INTO conversations(phone, started_at, kind) VALUES (?, ?, ?)",
                        (row["phone"], row["last_active"],
                         "pengaduan" if row["step"] == "operator" else "konsultasi"))
                    conn.execute("UPDATE sessions SET conversation_id=? WHERE phone=?",
                                 (cursor.lastrowid, row["phone"]))
                    conn.execute("UPDATE messages SET conversation_id=? WHERE phone=?",
                                 (cursor.lastrowid, row["phone"]))
            conn.execute("CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id, id)")
            conn.execute("PRAGMA user_version=2")
            conn.commit()
            os.chmod(DB_PATH, 0o600)
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
        conn.execute("DELETE FROM conversations")
        conn.execute("DELETE FROM webhook_inbox")
        conn.commit()
    finally:
        conn.close()
