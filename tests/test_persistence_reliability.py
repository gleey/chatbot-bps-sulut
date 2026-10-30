"""Archive migration, retention, concurrency and durable inbox regression tests."""
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests import support  # noqa: F401
import db
import main
import message_queue
from session_manager import SessionManager

PHONE = "6281234567890"


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        db.init_db()
        db.reset_db()
        self.manager = SessionManager()

    def test_reset_preserves_archive_and_isolates_new_history(self):
        self.manager.add_to_history(PHONE, "user", "old complaint")
        self.manager.set_step(PHONE, "operator")
        previous = self.manager.get_or_create(PHONE)["conversation_id"]
        self.manager.reset(PHONE)
        self.assertEqual(self.manager.get_history(PHONE), [])
        self.assertNotEqual(self.manager.get_or_create(PHONE)["conversation_id"], previous)
        self.assertEqual(self.manager.get_archives(PHONE)[0]["kind"], "pengaduan")
        with closing(db.get_conn()) as conn, conn:
            self.assertEqual(conn.execute("SELECT text FROM messages WHERE conversation_id=?", (previous,)).fetchone()[0], "old complaint")

    def test_restart_keeps_operator_and_history(self):
        self.manager.add_to_history(PHONE, "user", "help")
        self.manager.set_step(PHONE, "operator")
        db._initialized = False
        other = SessionManager()
        self.assertEqual(other.get_history(PHONE)[0]["parts"][0]["text"], "help")
        self.assertTrue(other.is_operator(PHONE))

    def test_expired_bot_archived_operator_not_expired(self):
        self.manager.add_to_history(PHONE, "user", "old")
        self.manager.get_or_create("6281234567891")
        self.manager.set_step("6281234567891", "operator")
        with closing(db.get_conn()) as conn, conn:
            conn.execute("UPDATE sessions SET last_active=?", (time.time() - 1000,))
        self.assertEqual(self.manager.get_expired_sessions(), [PHONE])
        self.assertFalse(self.manager.is_expired("6281234567891"))
        self.manager.cleanup_expired()
        self.assertEqual(self.manager.get_archives(PHONE)[0]["close_reason"], "timeout")
        self.assertTrue(self.manager.is_operator("6281234567891"))
        self.assertEqual(self.manager.count_active(), 1)

    def test_retention_only_purges_eligible_closed_archives(self):
        for phone in [PHONE, "6281234567891", "6281234567892"]:
            self.manager.add_to_history(phone, "user", "history")
        self.manager.reset(PHONE)
        self.manager.reset("6281234567891")
        with closing(db.get_conn()) as conn, conn:
            conn.execute("UPDATE conversations SET closed_at=? WHERE phone=?", (time.time() - 40 * 86400, PHONE))
        self.assertEqual(self.manager.purge_archives(30), 1)
        self.assertEqual(self.manager.get_archives(PHONE), [])
        self.assertEqual(len(self.manager.get_archives("6281234567891")), 1)
        self.assertEqual(len(self.manager.get_history("6281234567892")), 1)
        self.assertRaises(ValueError, self.manager.purge_archives, 0)

    def test_clear_tujuan(self):
        self.manager.update_info(PHONE, "inflasi")
        self.manager.update_info(PHONE, "")
        self.assertEqual(self.manager.get_or_create(PHONE)["tujuan"], "")

    def test_same_phone_fsm_calls_serialized(self):
        self.manager.set_step(PHONE, "operator")
        with ThreadPoolExecutor(max_workers=8) as executor:
            replies = list(executor.map(lambda i: main.handle_incoming_message(PHONE, f"complaint {i}"), range(20)))
        self.assertEqual(replies, [None] * 20)
        self.assertEqual(len(self.manager.get_history(PHONE)), 20)

    def test_new_phone_race_does_not_duplicate_active_conversation(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            sessions = list(executor.map(lambda _: self.manager.get_or_create(PHONE), range(20)))
        self.assertEqual(len({s["conversation_id"] for s in sessions}), 1)

    def test_legacy_migration_backs_up_without_losing_messages(self):
        with tempfile.TemporaryDirectory(prefix="bps-legacy-") as directory:
            path = os.path.join(directory, "legacy.db")
            with closing(sqlite3.connect(path)) as conn, conn:
                conn.executescript("""
                    CREATE TABLE sessions(phone TEXT PRIMARY KEY, tujuan TEXT, step TEXT, last_active REAL);
                    CREATE TABLE messages(id INTEGER PRIMARY KEY, phone TEXT, role TEXT, text TEXT, ts REAL,
                        FOREIGN KEY(phone) REFERENCES sessions(phone) ON DELETE CASCADE);
                    INSERT INTO sessions VALUES ('6281234567890', 'help', 'operator', 123);
                    INSERT INTO messages VALUES (1, '6281234567890', 'user', 'preserve me', 123);
                """)
            with patch.object(db, "DB_PATH", path), patch.object(db, "_initialized", False):
                manager = SessionManager()
                self.assertEqual(manager.get_history(PHONE)[0]["parts"][0]["text"], "preserve me")
                self.assertTrue(manager.is_operator(PHONE))
                manager.reset(PHONE)
                self.assertEqual(manager.get_archives(PHONE)[0]["kind"], "pengaduan")
                backups = list(Path(directory).glob("*.bak"))
                self.assertEqual(len(backups), 1)
                with closing(sqlite3.connect(backups[0])) as conn, conn:
                    self.assertEqual(conn.execute("SELECT text FROM messages").fetchone()[0], "preserve me")
                db._initialized = False
                db.init_db()
                self.assertEqual(len(list(Path(directory).glob("*.bak"))), 1)


class InboxTests(unittest.TestCase):
    def setUp(self):
        db.init_db()
        db.reset_db()

    def test_duplicate_concurrent_acceptance(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: message_queue.enqueue([("id1", PHONE, "hi")]), range(20)))
        self.assertEqual(sum(results), 1)

    def test_worker_logs_incoming_message_once_and_provider_acceptance(self):
        text = "Halo,\nsaya ingin konsultasi"
        message_queue.enqueue([("id1", PHONE, text)])
        handle = Mock(return_value={"message": "reply"})
        with self.assertLogs("message_queue", level="INFO") as logs:
            self.assertTrue(message_queue.process_next(handle, Mock(return_value=True)))
            self.assertFalse(message_queue.process_next(handle, Mock(return_value=True)))
        incoming = [line for line in logs.output if "Pesan masuk dari" in line]
        self.assertEqual(len(incoming), 1)
        self.assertIn(PHONE, incoming[0])
        self.assertIn("Halo,\\nsaya ingin konsultasi", incoming[0])
        self.assertNotIn("\n", incoming[0])
        self.assertTrue(any("Balasan diterima provider" in line for line in logs.output))
        handle.assert_called_once_with(PHONE, text)

    def test_worker_log_redacts_configured_secret_before_truncating(self):
        secret = "synthetic-secret-that-must-not-appear"
        text = "x" * 90 + secret
        message_queue.enqueue([("id1", PHONE, text)])
        with patch.object(message_queue.config, "META_APP_SECRET", secret), self.assertLogs("message_queue", level="INFO") as logs:
            message_queue.process_next(Mock(return_value=None), Mock())
        incoming = next(line for line in logs.output if "Pesan masuk dari" in line)
        self.assertNotIn("synthetic", incoming)
        self.assertIn("[REDACTED]", incoming)

    def test_worker_logs_handoff_without_sending_reply(self):
        message_queue.enqueue([("id1", PHONE, "Keluhan demo")])
        send = Mock()
        with self.assertLogs("message_queue", level="INFO") as logs:
            message_queue.process_next(Mock(return_value=None), send)
        send.assert_not_called()
        self.assertTrue(any("Diteruskan ke operator" in line for line in logs.output))
        self.assertFalse(any("Balasan diterima provider" in line for line in logs.output))

    def test_worker_logs_send_failure_without_success_claim(self):
        message_queue.enqueue([("id1", PHONE, "Halo")])
        with self.assertLogs("message_queue", level="INFO") as logs:
            message_queue.process_next(Mock(return_value={"message": "reply"}), Mock(return_value=False))
        self.assertTrue(any("Gagal mengirim balasan" in line for line in logs.output))
        self.assertFalse(any("Balasan diterima provider" in line for line in logs.output))

    def test_failed_delivery_not_automatically_replayed(self):
        message_queue.enqueue([("id1", PHONE, "hi")])
        handle, send = Mock(return_value={"message": "reply"}), Mock(return_value=False)
        self.assertTrue(message_queue.process_next(handle, send))
        self.assertEqual(message_queue.enqueue([("id1", PHONE, "hi")]), 0)
        self.assertFalse(message_queue.process_next(handle, send))
        self.assertEqual(handle.call_count, 1)
        with closing(db.get_conn()) as conn, conn:
            row = conn.execute("SELECT * FROM webhook_inbox").fetchone()
            self.assertEqual(row["status"], "failed")
            self.assertIn("reply", row["reply"])

    def test_pending_survives_reinitialization(self):
        message_queue.enqueue([("id1", PHONE, "hi")])
        db._initialized = False
        db.init_db()
        self.assertTrue(message_queue.pending_for(PHONE))
        self.assertTrue(message_queue.process_next(Mock(return_value=None), Mock()))

    def test_batch_acceptance_is_atomic_on_rate_limit(self):
        message_queue.enqueue([("id1", PHONE, "hi")])
        with self.assertRaises(message_queue.RateLimited):
            message_queue.enqueue([("id2", "6281234567891", "hi"), ("id3", PHONE, "hi again")])
        with closing(db.get_conn()) as conn, conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM webhook_inbox").fetchone()[0], 1)

    def test_processing_exception_is_isolated(self):
        message_queue.enqueue([("id1", PHONE, "hi"), ("id2", "6281234567891", "hi")])
        self.assertTrue(message_queue.process_next(Mock(side_effect=ValueError("synthetic")), Mock()))
        self.assertTrue(message_queue.process_next(Mock(return_value=None), Mock()))

    def test_worker_start_idempotent_and_crash_state_preserved(self):
        message_queue.enqueue([("id1", PHONE, "hi")])
        with closing(db.get_conn()) as conn, conn:
            conn.execute("UPDATE webhook_inbox SET status='processing'")
        with patch.object(message_queue, "_worker", None), patch.object(message_queue, "process_next", return_value=False):
            worker = message_queue.start_worker(Mock(), Mock())
            try:
                self.assertIs(message_queue.start_worker(Mock(), Mock()), worker)
                with closing(db.get_conn()) as conn, conn:
                    self.assertEqual(conn.execute("SELECT error FROM webhook_inbox").fetchone()[0], "interrupted_unknown")
            finally:
                message_queue._stop.set()
                worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
