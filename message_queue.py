"""Durable, bounded inbox for a single-process Flask/Waitress deployment."""
import json
import logging
import threading
import time

import config
from db import get_conn, init_db
from webhook_utils import phone_lock, RATE_LIMIT_SECONDS

logger = logging.getLogger(__name__)
MAX_PENDING = 1000
_worker = None
_worker_lock = threading.Lock()
_stop = threading.Event()


class InboxFull(Exception):
    pass


class RateLimited(Exception):
    pass


def enqueue(events):
    """Atomically accept a batch; event IDs remain deduplicated for seven days."""
    init_db()
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        now = time.time()
        conn.execute("DELETE FROM webhook_inbox WHERE status='done' AND created_at < ?", (now - 7 * 86400,))
        fresh = {}
        for event_id, phone, text in events:
            if not conn.execute("SELECT 1 FROM webhook_inbox WHERE event_id=?", (event_id,)).fetchone():
                fresh[event_id] = (phone, text)
        pending = conn.execute("SELECT COUNT(*) FROM webhook_inbox WHERE status IN ('queued','processing')").fetchone()[0]
        if pending + len(fresh) > MAX_PENDING:
            raise InboxFull
        for phone in {value[0] for value in fresh.values()}:
            recent = conn.execute("SELECT 1 FROM webhook_inbox WHERE phone=? AND created_at > ? LIMIT 1",
                                  (phone, now - RATE_LIMIT_SECONDS)).fetchone()
            if recent:
                raise RateLimited
        conn.executemany("INSERT INTO webhook_inbox(event_id, phone, text, created_at) VALUES (?, ?, ?, ?)",
                         [(event_id, phone, text, now) for event_id, (phone, text) in fresh.items()])
        conn.commit()
        return len(fresh)
    finally:
        conn.close()


def pending_for(phone):
    conn = get_conn()
    try:
        return conn.execute("SELECT 1 FROM webhook_inbox WHERE phone=? AND status IN ('queued','processing') LIMIT 1",
                            (phone,)).fetchone() is not None
    finally:
        conn.close()


def process_next(handle, send):
    """Process once. Ambiguous sends are never automatically replayed."""
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM webhook_inbox WHERE status='queued' ORDER BY created_at, rowid LIMIT 1").fetchone()
        if row is None:
            return False
        conn.execute("UPDATE webhook_inbox SET status='processing' WHERE event_id=?", (row["event_id"],))
        conn.commit()
    finally:
        conn.close()
    status, error = "failed", "processing_failed"
    try:
        with phone_lock(row["phone"]):
            preview = row["text"]
            for secret in [*config.GEMINI_API_KEYS, config.GEMINI_API_KEY, config.META_ACCESS_TOKEN,
                           config.META_APP_SECRET, config.META_VERIFY_TOKEN, config.FONNTE_TOKEN,
                           config.FONNTE_WEBHOOK_SECRET, config.BPS_API_KEY, config.FLASK_SECRET_KEY,
                           config.OPERATOR_PASSWORD_HASH]:
                if secret:
                    preview = preview.replace(secret, "[REDACTED]")
            logger.info("Pesan masuk dari [%s]: %r", row["phone"], preview[:100])
            reply = handle(row["phone"], row["text"])
            conn = get_conn()
            try:
                conn.execute("UPDATE webhook_inbox SET reply=? WHERE event_id=?", (json.dumps(reply), row["event_id"]))
                conn.commit()
            finally:
                conn.close()
            if reply is None:
                logger.info("Diteruskan ke operator: %s", row["phone"])
                status, error = "done", None
            elif send(row["phone"], reply):
                logger.info("Balasan diterima provider untuk %s", row["phone"])
                status, error = "done", None
            else:
                logger.warning("Gagal mengirim balasan ke %s; periksa provider sebelum mengulang", row["phone"])
                error = "delivery_failed_or_unknown"
    except Exception as exc:
        logger.error("Inbox processing failed (%s)", type(exc).__name__)
    conn = get_conn()
    try:
        conn.execute("UPDATE webhook_inbox SET status=?, error=? WHERE event_id=?", (status, error, row["event_id"]))
        conn.commit()
    finally:
        conn.close()
    return True


def start_worker(handle, send):
    global _worker
    with _worker_lock:
        if _worker is not None and _worker.is_alive():
            return _worker
        init_db()
        conn = get_conn()
        try:
            # A crash may happen after a provider accepted a send. Require manual reconciliation.
            conn.execute("UPDATE webhook_inbox SET status='failed', error='interrupted_unknown' WHERE status='processing'")
            conn.commit()
        finally:
            conn.close()
        _stop.clear()

        def loop():
            while not _stop.is_set():
                try:
                    if process_next(handle, send):
                        continue
                except Exception as exc:
                    logger.error("Inbox worker unavailable (%s)", type(exc).__name__)
                _stop.wait(0.25)

        _worker = threading.Thread(target=loop, daemon=True, name="WebhookInboxWorker")
        _worker.start()
        return _worker


def worker_running():
    return _worker is not None and _worker.is_alive()
