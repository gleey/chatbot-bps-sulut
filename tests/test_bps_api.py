"""Tests untuk BPS Web API client, direct subcsa filtering, pre-warming, dan SQLite caching."""
import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db as database
database.DB_PATH = "/tmp/opencode/test_bps_api_%d.db" % os.getpid()
database._initialized = False
database.init_db()

import bps_api


class TestBpsApi(unittest.TestCase):

    def setUp(self):
        database._initialized = False
        database.init_db()
        database.reset_db()

    def tearDown(self):
        database.reset_db()

    def test_clean_html(self):
        html = "<ul><li>Test 1</li><li>Test 2</li></ul>"
        clean = bps_api._clean_html(html)
        self.assertIn("• Test 1", clean)
        self.assertNotIn("<ul>", clean)

    def test_cache_set_and_get(self):
        key = "test_cache_key_123"
        data = {"status": "OK", "data": [1, 2, 3]}
        bps_api._cache_set(key, data)

        cached = bps_api._cache_get(key)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["status"], "OK")

    def test_cache_expiration(self):
        key = "test_cache_expired"
        data = {"status": "OK"}
        bps_api._cache_set(key, data)

        # Manually expire entry in SQLite
        conn = database.get_conn()
        conn.execute("UPDATE bps_cache SET ts=? WHERE cache_key=?", (time.time() - 90000, key))
        conn.commit()
        conn.close()

        cached = bps_api._cache_get(key)
        self.assertIsNone(cached)

    @patch("bps_api.requests.get")
    def test_cari_data_bps_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "OK",
            "data": [
                {"page": 1},
                [
                    {
                        "brs_id": 100,
                        "title": "Tingkat Pengangguran Terbuka 2026",
                        "subcsa": "Tenaga Kerja",
                        "abstract": "<ul><li>TPT sebesar 5,85 persen</li></ul>",
                        "rl_date": "2026-08-05",
                        "pdf": "https://bps.go.id/test.pdf"
                    }
                ]
            ]
        }
        mock_get.return_value = mock_resp

        res = bps_api.cari_data_bps("pengangguran")
        self.assertIsNotNone(res)
        self.assertTrue(res["found"])
        self.assertIn("Pengangguran", res["title"])
        self.assertIn("5,85 persen", res["naratif"])
        self.assertEqual(res["link_pdf"], "https://bps.go.id/test.pdf")

    @patch("bps_api.requests.get")
    def test_prewarm_cache(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "OK", "data": [{"page": 1}, []]}
        mock_get.return_value = mock_resp

        bps_api.prewarm_cache()
        self.assertTrue(mock_get.called)
        self.assertGreaterEqual(mock_get.call_count, 5)

    @patch("bps_api.requests.get")
    def test_cari_data_bps_no_match(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "OK",
            "data": [{"page": 1}, []]
        }
        mock_get.return_value = mock_resp

        res = bps_api.cari_data_bps("xyz_unknown_keyword_123")
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
