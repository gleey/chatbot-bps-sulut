"""Tests untuk state machine — alur percakapan lengkap."""
import os
import sys
import unittest
from contextlib import closing
from unittest.mock import patch

# Setup test DB
os.environ.setdefault("TESTING", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests import support  # noqa: F401; isolate environment before application imports

import db as database
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
        set_offline_mode(True)
        for name, value in [("main.cari_data_bps", None), ("main.cari_tabel_terbaru_bps", [])]:
            mock = patch(name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

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
        self.assertIn("statistics-table", result["message"])

    @patch("main.is_jam_kerja", return_value=True)
    @patch("main.is_offline_mode", return_value=True)
    def test_pengaduan_flow_jam_kerja(self, mock_offline, mock_jam):
        """Pilih pengaduan saat jam kerja → diteruskan ke operator."""
        handle_incoming_message(self.phone, "halo")
        result = handle_incoming_message(self.phone, "Pengaduan")
        self.assertIn("operator", result["message"].lower())

    @patch("main.is_jam_kerja", return_value=False)
    @patch("main.is_offline_mode", return_value=True)
    def test_pengaduan_flow_luar_jam_kerja(self, mock_offline, mock_jam):
        """Pilih pengaduan di luar jam kerja → pesan permohonan maaf & kontak."""
        handle_incoming_message(self.phone, "halo")
        result = handle_incoming_message(self.phone, "Pengaduan")
        self.assertIn("luar jam kerja", result["message"].lower())
        self.assertIn("bps7100@bps.go.id", result["message"])
        self.assertEqual(session_mgr.get_archives(self.phone)[-1]["kind"], "pengaduan")

    @patch("main.is_jam_kerja", return_value=True)
    def test_tidak_puas_jam_kerja(self, mock_jam):
        """Tidak puas saat jam kerja → diteruskan ke operator."""
        handle_incoming_message(self.phone, "halo")
        handle_incoming_message(self.phone, "Konsultasi")
        handle_incoming_message(self.phone, "kependudukan")
        result = handle_incoming_message(self.phone, "Tidak")
        self.assertIn("operator", result["message"].lower())

    @patch("main.is_jam_kerja", return_value=False)
    def test_tidak_puas_luar_jam_kerja(self, mock_jam):
        """Tidak puas di luar jam kerja → permohonan maaf & kontak."""
        handle_incoming_message(self.phone, "halo")
        handle_incoming_message(self.phone, "Konsultasi")
        handle_incoming_message(self.phone, "kependudukan")
        result = handle_incoming_message(self.phone, "Tidak")
        self.assertIn("luar jam kerja", result["message"].lower())

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

    def test_selesai_in_every_state_archives_and_resets(self):
        from main import STATES
        for step in STATES:
            session_mgr.set_step(self.phone, step)
            result = handle_incoming_message(self.phone, "Selesai")
            self.assertIn("Terima kasih", result["message"])
            self.assertEqual(session_mgr.get_or_create(self.phone)["step"], "awal")

    def test_ya_resumes_consultation_and_invalid_answer_stays(self):
        session_mgr.set_step(self.phone, "tanya_kepuasan")
        handle_incoming_message(self.phone, "mungkin")
        self.assertEqual(session_mgr.get_or_create(self.phone)["step"], "tanya_kepuasan")
        handle_incoming_message(self.phone, "Ya")
        self.assertEqual(session_mgr.get_or_create(self.phone)["step"], "rule_based_tanya_data")

    def test_expired_session_returns_menu(self):
        import time
        session_mgr.set_step(self.phone, "tanya_kepuasan")
        with closing(database.get_conn()) as conn, conn:
            conn.execute("UPDATE sessions SET last_active=?", (time.time() - 1000,))
        handle_incoming_message(self.phone, "Ya")
        self.assertEqual(session_mgr.get_or_create(self.phone)["step"], "pilih_layanan")

    def test_working_hours_wita_boundaries_and_weekend(self):
        from datetime import datetime
        from main import is_jam_kerja, WITA
        for day, hour, minute, expected in [(26, 7, 59, False), (26, 8, 0, True),
                                            (26, 15, 30, True), (26, 15, 31, False), (31, 10, 0, False)]:
            with patch("main.datetime") as clock:
                clock.now.return_value = datetime(2026, 10, day, hour, minute, tzinfo=WITA)
                self.assertEqual(is_jam_kerja(), expected)


if __name__ == "__main__":
    unittest.main()
