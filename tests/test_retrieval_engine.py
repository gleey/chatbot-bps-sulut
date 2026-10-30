"""Grounding, BPS response validation and bounded Gemini fallback tests."""
import os
import sys
import time
import unittest
from contextlib import closing
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests import support  # noqa: F401
import bps_api
import db
import llm_engine as engine
import main
from google.genai import errors


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        db.init_db()
        db.reset_db()

    @patch("bps_api.requests.get")
    def test_bps_cache_hit_avoids_http_and_expiry_refetches(self, get):
        get.return_value.json.return_value = {"status": "OK", "data": [{}, []]}
        first = bps_api._request_bps("list/model/statictable/domain/7100")
        self.assertEqual(bps_api._request_bps("list/model/statictable/domain/7100"), first)
        self.assertEqual(get.call_count, 1)
        with closing(db.get_conn()) as conn, conn:
            conn.execute("UPDATE bps_cache SET ts=?", (time.time() - 90000,))
        bps_api._request_bps("list/model/statictable/domain/7100")
        self.assertEqual(get.call_count, 2)

    @patch("bps_api.requests.get")
    def test_failed_and_malformed_bps_responses_not_cached(self, get):
        import requests
        for value in [[], {"status": "ERROR"}, None]:
            get.return_value.json.return_value = value
            self.assertIsNone(bps_api._request_bps("list/model/statictable/domain/7100"))
        get.side_effect = requests.Timeout("https://example.test/key/sensitive-key")
        with self.assertLogs("bps_api", level="WARNING") as logs:
            self.assertIsNone(bps_api._request_bps("list/model/statictable/domain/7100"))
        self.assertNotIn("sensitive-key", " ".join(logs.output))

    def test_official_urls_reject_spoofing_and_credentials(self):
        for url in ["https://bps.go.id.evil.test/fake", "javascript:alert(1)", "https://user@bps.go.id/secret", "http://bps.go.id/file", "https://bps.go.id:bad/file", "https://webapi.bps.go.id/key/test-bps-key/"]:
            self.assertEqual(bps_api._official_url(url), "")
        self.assertEqual(bps_api._official_url("https://sulut.bps.go.id/table"), "https://sulut.bps.go.id/table")

    def test_official_tables_precede_server_action_and_rank_returned_page(self):
        data = {"data": [{}, [
            {"title": "Penduduk 2023", "updt_date": "2023-01-01", "excel": "https://bps.go.id/old.xlsx"},
            {"title": "Penduduk 2025", "updt_date": "2025-01-01", "excel": "https://bps.go.id/new.xlsx"},
            {"title": "Pariwisata", "updt_date": "2026-01-01", "excel": "https://evil.test/false"}]]}
        with patch("bps_api._request_bps", return_value=data), patch("bps_api.requests.post") as post:
            result = bps_api.cari_tabel_terbaru_bps("penduduk")
        self.assertEqual([row["title"] for row in result], ["Penduduk 2025", "Penduduk 2023"])
        self.assertEqual(result[0]["source_type"], "unduhan resmi")
        post.assert_not_called()

    def test_table_year_and_keyword_must_match(self):
        with patch("bps_api._request_bps", return_value={"data": [{}, [{"title": "Penduduk 2023"}]]}):
            self.assertEqual(bps_api.cari_tabel_terbaru_bps("penduduk 2025"), [])
            self.assertEqual(bps_api.cari_tabel_terbaru_bps(""), [])

    def test_catalog_is_labelled_when_individual_url_missing(self):
        with patch("bps_api._request_bps", return_value={"data": [{}, [{"title": "Jumlah Penduduk"}]]}):
            result = bps_api.cari_tabel_terbaru_bps("penduduk", "https://sulut.bps.go.id/id/statistics-table?subject=519")
        self.assertEqual(result[0]["source_type"], "katalog subjek")

    def test_server_action_failure_and_invalid_items_fall_back_safely(self):
        import requests
        with patch("bps_api._request_bps", return_value=None), patch("bps_api.BPS_SERVER_ACTION_ID", "synthetic"), patch("bps_api.requests.post", side_effect=requests.Timeout("synthetic")):
            self.assertEqual(bps_api.cari_tabel_terbaru_bps("inflasi"), [])
        for malformed in [None, [], {"data": {}}, {"data": [1, [None, {"title": None}]]}]:
            with patch("bps_api._request_bps", return_value=malformed):
                self.assertEqual(bps_api.cari_tabel_terbaru_bps("inflasi"), [])
                self.assertIsNone(bps_api.cari_data_bps("inflasi"))

    def test_server_action_uses_only_returned_official_urls(self):
        import json
        envelope = {"response": {"data": [{}, [
            {"title": "Inflasi", "id": 1, "tablesource": 3},
            {"title": "Inflasi", "url": "https://evil.test/false"},
            {"title": "Inflasi", "url": "https://sulut.bps.go.id/official-table"}]]}}
        response = Mock(text="1:" + json.dumps(envelope))
        with patch("bps_api._request_bps", return_value=None), patch("bps_api.BPS_SERVER_ACTION_ID", "synthetic"), patch("bps_api.requests.post", return_value=response):
            result = bps_api.cari_tabel_terbaru_bps("inflasi")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["url"], "https://sulut.bps.go.id/official-table")

    def test_generated_numbers_and_urls_never_displayed(self):
        phone = "6281234567890"
        main.session_mgr.set_step(phone, "gemini_tanya_data")
        generated = {"intent": "cari_data", "tujuan": "inflasi", "balasan": "Angka palsu 999.123 https://evil.test", "kategori_cocok": "inflasi"}
        official = {"found": True, "title": "Inflasi 2025", "tanggal": "2025-01-01", "naratif": "Angka fixture resmi 1,23 persen", "link_pdf": "https://bps.go.id/test.pdf"}
        with patch("main.analisis_pesan", return_value=generated), patch("main.cari_data_bps", return_value=official), patch("main.cari_tabel_terbaru_bps", return_value=[]):
            result = main.handle_incoming_message(phone, "inflasi")
        self.assertNotIn("999.123", result["message"])
        self.assertNotIn("evil.test", result["message"])
        self.assertIn("1,23 persen", result["message"])
        self.assertIn("2025-01-01", result["message"])
        self.assertIn("cache maksimal 24 jam", result["message"])
        self.assertEqual(sum(m["role"] == "user" for m in main.session_mgr.get_history(phone)), 1)


class EngineTests(unittest.TestCase):
    def setUp(self):
        engine.set_offline_mode(False)
        self.keys = patch.object(engine, "_key_rotator", engine._KeyRotator(["synthetic-a", "synthetic-b"]))
        self.models = patch.object(engine, "_model_rotator", engine._ModelRotator(["model-a", "model-b"]))
        self.keys.start()
        self.models.start()
        self.addCleanup(self.keys.stop)
        self.addCleanup(self.models.stop)

    def test_request_timeout_and_retry_budget_configured(self):
        with patch("llm_engine.genai.Client") as client:
            engine._call_gemini([], "synthetic")
            options = client.call_args.kwargs["http_options"]
            self.assertLessEqual(options.timeout, engine.GEMINI_TIMEOUT_SECONDS * 1000)
            self.assertGreaterEqual(options.timeout, 10000)
            self.assertEqual(options.retry_options.attempts, 1)
            client.return_value.close.assert_called_once()

    def test_old_sdk_reports_dependency_error_before_connecting(self):
        with patch.object(engine, "types") as types, patch("llm_engine.genai.Client") as client:
            del types.HttpOptions
            with self.assertRaisesRegex(RuntimeError, "SDK Gemini terlalu lama"):
                engine._call_gemini([], "synthetic")
            client.assert_not_called()

    def test_retries_are_bounded_and_keys_keep_cooldown(self):
        with patch("llm_engine.genai.Client") as client, patch.object(engine, "GEMINI_MAX_ATTEMPTS", 1):
            client.return_value.models.generate_content.side_effect = errors.ClientError(429, {"error": {"message": "quota"}})
            self.assertRaises(RuntimeError, engine._call_gemini, [], "synthetic")
            self.assertEqual(client.return_value.models.generate_content.call_count, 1)
        self.assertIn(0, engine._key_rotator.failed)

    def test_server_error_tries_another_model(self):
        with patch("llm_engine.genai.Client") as client:
            client.return_value.models.generate_content.side_effect = [errors.ServerError(503, {"error": {"message": "unavailable"}}), Mock(text="{}")]
            engine._call_gemini([], "synthetic")
            self.assertEqual(client.return_value.models.generate_content.call_args.kwargs["model"], "model-b")

    def test_fallback_stops_before_sending_a_deadline_shorter_than_ten_seconds(self):
        with patch("llm_engine.genai.Client") as client, patch.object(engine, "GEMINI_TIMEOUT_SECONDS", 15), patch("llm_engine.time.monotonic", side_effect=[0, 0, 6]):
            client.return_value.models.generate_content.side_effect = errors.ClientError(404, {"error": {"message": "missing"}})
            self.assertRaises(RuntimeError, engine._call_gemini, [], "synthetic")
            self.assertEqual(client.return_value.models.generate_content.call_count, 1)
            self.assertEqual(client.call_args.kwargs["http_options"].timeout, 15000)

    def test_rejected_request_keeps_error_detail_without_exposing_key(self):
        secret = "synthetic-sensitive-api-key"
        error = errors.ClientError(400, {"error": {"message": f"Invalid argument\nkey={secret}"}})
        with patch.object(engine, "GEMINI_API_KEYS", [secret]), patch("llm_engine.genai.Client") as client:
            client.return_value.models.generate_content.side_effect = error
            with self.assertLogs("llm_engine", level="WARNING") as logs:
                with self.assertRaises(engine._GeminiRequestError) as caught:
                    engine._call_gemini([], "synthetic")
        self.assertIn("Invalid argument", str(caught.exception))
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn(secret, " ".join(logs.output))
        self.assertNotIn("\n", str(caught.exception))
        self.assertIn("model=model-a, key #1", logs.output[0])
        self.assertEqual(client.return_value.models.generate_content.call_count, 1)
        self.assertEqual(engine._key_rotator.failed, {})
        self.assertEqual(engine._model_rotator.failed, {})

    def test_bad_request_does_not_disable_gemini_for_next_message(self):
        history = [{"role": "user", "parts": [{"text": "data inflasi"}]}]
        error = errors.ClientError(400, {"error": {"message": "Invalid argument"}})
        with patch("llm_engine.genai.Client") as client:
            client.return_value.models.generate_content.side_effect = [
                error, Mock(text='{"intent":"cari_data","balasan":"valid"}')]
            with self.assertLogs("llm_engine", level="WARNING") as logs:
                self.assertEqual(engine.analisis_pesan(history)["intent"], "cari_data")
            self.assertFalse(engine.is_offline_mode())
            self.assertFalse(any("Semua key" in line for line in logs.output))
            self.assertEqual(engine.analisis_pesan(history)["balasan"], "valid")
            self.assertEqual(client.return_value.models.generate_content.call_count, 2)

    def test_connection_error_stops_and_does_not_leak_credentials(self):
        with patch("llm_engine.genai.Client", side_effect=OSError("sensitive-api-key")) as client:
            with self.assertRaises(RuntimeError) as error:
                engine._call_gemini([], "synthetic")
            self.assertNotIn("sensitive-api-key", str(error.exception))
            self.assertEqual(client.call_count, 1)

    def test_invalid_json_and_wrong_shapes_use_rules(self):
        history = [{"role": "user", "parts": [{"text": "data inflasi"}]}]
        for text in ["not JSON", "[]", "null", '{"intent": "cari_data", "tujuan": []}', '{"intent":"invalid"}', '"string"']:
            with patch("llm_engine._call_gemini", return_value=Mock(text=text)):
                self.assertEqual(engine.analisis_pesan(history)["intent"], "cari_data")

    def test_offline_recovers_after_cooldown(self):
        engine.set_offline_mode(True)
        self.assertTrue(engine.is_offline_mode())
        with patch.object(engine, "_offline_since", time.monotonic() - engine.ROTATOR_COOLDOWN - 1):
            self.assertFalse(engine.is_offline_mode())

    def test_context_roles_filtered_and_history_bounded(self):
        history = [{"role": "model" if i % 2 else "user", "parts": [{"text": f"message {i}"}]} for i in range(100)]
        history.insert(0, {"role": "operator", "parts": [{"text": "private operator note"}]})
        with patch("llm_engine._call_gemini", return_value=Mock(text='{"intent":"cari_data"}')) as call:
            engine.analisis_pesan(history)
            self.assertEqual(len(call.call_args.args[0]), 30)
