"""Tests untuk state machine — alur percakapan lengkap."""
import os
import sys
import unittest
from unittest.mock import patch

# Setup test DB
os.environ.setdefault("TESTING", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db as database
database.DB_PATH = "/tmp/opencode/test_state_%d.db" % os.getpid()
database._initialized = False
database.init_db()

from main import handle_incoming_message, session_mgr


class TestStateMachine(unittest.TestCase):

    def setUp(self):
        database._initialized = False
        database.init_db()
        database.reset_db()
        self.phone = "08999"
        # Reset offline mode (test rotator bisa menyetelnya)
        from llm_engine import set_offline_mode
        set_offline_mode(False)

    def tearDown(self):
        database.reset_db()

    def test_awal_greeting(self):
        """Step awal → tanya pilih layanan."""
        result = handle_incoming_message(self.phone, "halo")
        self.assertIn("Selamat datang", result["message"])
        self.assertIn("buttons", result)
        s = session_mgr.get_or_create(self.phone)
        self.assertEqual(s["step"], "pilih_layanan")

    def test_pilih_konsultasi_offline(self):
        """Pilih konsultasi saat offline → rule_based_tanya_data."""
        handle_incoming_message(self.phone, "halo")
        with patch("main.is_offline_mode", return_value=True):
            result = handle_incoming_message(self.phone, "Konsultasi")
        self.assertIn("Offline", result["message"])
        s = session_mgr.get_or_create(self.phone)
        self.assertEqual(s["step"], "rule_based_tanya_data")

    @patch("main.is_offline_mode", return_value=True)
    def test_rule_based_data_search(self, mock_offline):
        """Rule-based: cari data kependudukan → dapat link."""
        handle_incoming_message(self.phone, "halo")
        handle_incoming_message(self.phone, "Konsultasi")
        result = handle_incoming_message(self.phone, "kependudukan")
        self.assertIn("subject=519", result["message"])

    @patch("main.is_offline_mode", return_value=True)
    def test_pengaduan_flow(self, mock_offline):
        """Pilih pengaduan → operator."""
        handle_incoming_message(self.phone, "halo")
        result = handle_incoming_message(self.phone, "Pengaduan")
        self.assertIn("pengaduan", result["message"].lower())
        self.assertIn("bps7100@bps.go.id", result["message"])

    @patch("main.is_offline_mode", return_value=True)
    def test_invalid_layanan(self, mock_offline):
        """Input tidak valid → pesan error."""
        handle_incoming_message(self.phone, "halo")
        result = handle_incoming_message(self.phone, "xyz")
        self.assertIn("tidak valid", result["message"].lower())

    def test_invalid_step_resets(self):
        """Step tidak dikenal → reset otomatis."""
        session_mgr.get_or_create(self.phone)
        session_mgr.set_step(self.phone, "invalid_step_xyz")
        result = handle_incoming_message(self.phone, "test")
        self.assertIn("kesalahan sesi", result["message"].lower())


if __name__ == "__main__":
    unittest.main()
