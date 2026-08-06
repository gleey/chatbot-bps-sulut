"""Tests untuk SessionManager (SQLite-backed)."""
import os
import sys
import unittest

# Gunakan DB terpisah untuk testing
os.environ.setdefault("TESTING", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db as database
database.DB_PATH = "/tmp/opencode/test_chatbot_%d.db" % os.getpid()
database._initialized = False
database.init_db()

from session_manager import SessionManager


class TestSessionManager(unittest.TestCase):
    def setUp(self):
        database._initialized = False
        database.init_db()
        database.reset_db()
        self.mgr = SessionManager()
        self.phone = "08111111111"

    def tearDown(self):
        database.reset_db()

    def test_create_session(self):
        s = self.mgr.get_or_create(self.phone)
        self.assertEqual(s["step"], "awal")
        self.assertEqual(s["tujuan"], "")
        self.assertEqual(s["history"], [])

    def test_get_existing_session(self):
        self.mgr.get_or_create(self.phone)
        self.mgr.update_info(self.phone, tujuan="kependudukan")
        s = self.mgr.get_or_create(self.phone)
        self.assertEqual(s["tujuan"], "kependudukan")

    def test_update_info(self):
        self.mgr.get_or_create(self.phone)
        self.mgr.update_info(self.phone, tujuan="kependudukan")
        s = self.mgr.get_or_create(self.phone)
        self.assertEqual(s["tujuan"], "kependudukan")

    def test_set_step(self):
        self.mgr.get_or_create(self.phone)
        self.mgr.set_step(self.phone, "pilih_layanan")
        s = self.mgr.get_or_create(self.phone)
        self.assertEqual(s["step"], "pilih_layanan")

    def test_history(self):
        self.mgr.get_or_create(self.phone)
        self.mgr.add_to_history(self.phone, "user", "halo")
        self.mgr.add_to_history(self.phone, "model", "hi!")
        h = self.mgr.get_history(self.phone)
        self.assertEqual(len(h), 2)
        self.assertEqual(h[0]["role"], "user")
        self.assertEqual(h[0]["parts"][0]["text"], "halo")
        self.assertEqual(h[1]["role"], "model")

    def test_reset(self):
        self.mgr.get_or_create(self.phone)
        self.mgr.update_info(self.phone, tujuan="Test")
        self.mgr.add_to_history(self.phone, "user", "hi")
        self.mgr.reset(self.phone)
        s = self.mgr.get_or_create(self.phone)
        self.assertEqual(s["tujuan"], "")
        self.assertEqual(s["history"], [])

    def test_is_expired_false(self):
        self.mgr.get_or_create(self.phone)
        self.mgr.touch(self.phone)
        self.assertFalse(self.mgr.is_expired(self.phone))

    def test_active_bot_full_reset(self):
        self.mgr.get_or_create(self.phone)
        self.mgr.update_info(self.phone, tujuan="Old")
        self.mgr.add_to_history(self.phone, "user", "test")
        self.mgr.set_step(self.phone, "tanya_kepuasan")
        s = self.mgr.active_bot(self.phone)
        self.assertEqual(s["step"], "awal")
        self.assertEqual(s["tujuan"], "")
        self.assertEqual(s["history"], [])

    def test_count_active(self):
        self.mgr.get_or_create("081")
        self.mgr.touch("081")
        self.mgr.get_or_create("082")
        self.mgr.touch("082")
        self.assertEqual(self.mgr.count_active(), 2)

    def test_info_summary(self):
        self.mgr.get_or_create(self.phone)
        self.assertEqual(self.mgr.get_info_summary(self.phone), "Belum ada info")
        self.mgr.update_info(self.phone, tujuan="Test")
        self.assertIn("Tujuan: Test", self.mgr.get_info_summary(self.phone))


if __name__ == "__main__":
    unittest.main()
