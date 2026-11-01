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
from config import BPS_CATEGORIES
from urllib.parse import parse_qs, urlsplit
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

    def test_csa_categories_find_tables_by_subject_without_title_keyword(self):
        subjects = {}
        for keyword, url in BPS_CATEGORIES.items():
            subjects.setdefault(parse_qs(urlsplit(url).query)["subject"][0], keyword)
        self.assertEqual(len(subjects), 37)
        for subject, keyword in subjects.items():
            with self.subTest(keyword=keyword):
                rows = [
                    {"id": "MTc4MSMy", "title": "Indikator A", "subject": keyword.title(),
                     "id_subject": subject, "tablesource": "2", "last_update": "2026-09-01 10:00:00"},
                    {"id": "MTc4MiMy", "title": "Indikator B", "subject": keyword.title(),
                     "id_subject": subject, "tablesource": "2", "last_update": "2026-08-01 10:00:00"},
                ]
                with patch("bps_api._request_bps", return_value={"data": [{"pages": 1}, rows]}) as request, patch("bps_api.requests.post") as post:
                    result = bps_api.cari_tabel_terbaru_bps(keyword, f"https://sulut.bps.go.id/id/statistics-table?subject={subject}")
                    self.assertEqual([row["title"] for row in result], ["Indikator A", "Indikator B"])
                    self.assertEqual(request.call_args.kwargs["subject"], str(subject))
                    self.assertIn("tablestatistic", request.call_args.args[0])
                    self.assertTrue(all("/statistics-table/2/" in row["url"] for row in result))
                    post.assert_not_called()

    def test_csa_paginates_before_selecting_two_top_tables(self):
        def item(identifier, title, date, subject=521):
            return {"id": identifier, "title": title, "subject": "Pendidikan", "id_subject": subject,
                    "tablesource": "2", "last_update": date}
        first = {"data": [{"pages": 2}, [item("old", "Sekolah lama", "2020-01-01")]]}
        second = {"data": [{"pages": 2}, [
            item("third", "Indikator Z", "2026-09-01"),
            item("second", "Indikator B", "2026-09-01"),
            item("first", "Indikator A", "2026-09-01"),
            item("other-subject", "Data lain", "2026-10-01", subject=522),
        ]]}
        with patch("bps_api._request_bps", side_effect=[first, second]) as request:
            result = bps_api.cari_tabel_terbaru_bps("data terkait pendidikan")
        self.assertEqual([row["title"] for row in result], ["Indikator A", "Indikator B"])
        self.assertEqual([call.kwargs["page"] for call in request.call_args_list], [1, 2])

    def test_csa_requested_year_uses_available_range_and_table_url(self):
        row = {"id": "example", "title": "Angka Partisipasi Sekolah", "subject": "Pendidikan",
               "tablesource": "3", "oldest_period": 2020, "latest_period": 2025,
               "last_update": "2026-09-01"}
        with patch("bps_api._request_bps", return_value={"data": [{}, [row]]}):
            result = bps_api.cari_tabel_terbaru_bps("pendidikan 2024")
            self.assertEqual(len(result), 1)
            self.assertTrue(result[0]["url"].endswith("?year=2024"))
            self.assertEqual(bps_api.cari_tabel_terbaru_bps("pendidikan 2027"), [])

    def test_csa_table_link_rejects_invalid_source_and_identifier(self):
        for values in [{"tablesource": "9", "id": "valid"}, {"tablesource": "3", "id": None},
                       {"tablesource": "3", "id": "../fake"}, {"tablesource": "3", "id": "https://evil.test"}]:
            self.assertEqual(bps_api._csa_table_url({"title": "Indikator", **values}), "")

    def test_csa_cache_skips_second_network_lookup(self):
        row = {"id": "example", "title": "Indikator", "subject": "Pendidikan", "tablesource": "2"}
        with patch("bps_api._request_bps", return_value={"data": [{}, [row]]}) as request:
            first = bps_api.cari_tabel_terbaru_bps("pendidikan")
            self.assertEqual(bps_api.cari_tabel_terbaru_bps("pendidikan"), first)
            self.assertEqual(request.call_count, 1)

    def test_csa_failure_keeps_legacy_api_fallback(self):
        legacy = {"data": [{}, [{"title": "Data Pendidikan", "url": "https://sulut.bps.go.id/official-table"}]]}
        with patch("bps_api._request_bps", side_effect=[None, None, legacy]) as request:
            result = bps_api.cari_tabel_terbaru_bps("pendidikan")
        self.assertEqual(result[0]["url"], "https://sulut.bps.go.id/official-table")
        self.assertIn("statictable", request.call_args.args[0])

    def test_aliases_match_full_official_titles_without_unrelated_substrings(self):
        for query, title in [("kb", "Peserta Keluarga Berencana"),
                             ("bansos", "Anggaran Bantuan Sosial Pangan"),
                             ("pns", "Jumlah Pegawai Negeri Sipil"),
                             ("wisman", "Jumlah Wisatawan Mancanegara"),
                             ("tpk", "Tingkat Penghunian Kamar Bintang"),
                             ("ikk", "Indeks Kemahalan Konstruksi"),
                             ("pdrb", "Produk Domestik Regional Bruto"),
                             ("suhu udara", "Keadaan Suhu di Manado"),
                             ("data pendidkan sulut", "Angka Partisipasi Sekolah Pendidikan")]:
            with self.subTest(query=query):
                self.assertTrue(bps_api._matches(query, title))
        self.assertFalse(bps_api._matches("asi", "Transportasi"))
        self.assertFalse(bps_api._matches("penduduk 2025", "Penduduk 2023"))

    def test_missing_subject_match_searches_across_categories(self):
        row = {"id": "example", "title": "Produksi Kopra", "subject": "Pertanian",
               "id_subject": 557, "tablesource": "2"}
        with patch("bps_api._request_bps", side_effect=[None, {"data": [{}, [row]]}]) as request:
            result = bps_api.cari_tabel_terbaru_bps("kopra", "https://sulut.bps.go.id/id/statistics-table?subject=538")
        self.assertEqual(result[0]["title"], "Produksi Kopra")
        self.assertNotIn("subject", request.call_args.kwargs)

    def test_global_search_includes_tables_beyond_tenth_page(self):
        def response(endpoint, **params):
            rows = [{"id": "example", "title": "Fasilitas Olahraga", "tablesource": "2"}] if params["page"] == 13 else []
            return {"data": [{"pages": 13}, rows]}
        with patch("bps_api._request_bps", side_effect=response):
            result = bps_api.cari_tabel_terbaru_bps("olahraga")
        self.assertEqual(result[0]["title"], "Fasilitas Olahraga")

    def test_config_and_api_subject_mappings_agree(self):
        for keyword, (_, subject) in bps_api.KEYWORD_SUBJECT_MAP.items():
            if keyword in BPS_CATEGORIES:
                with self.subTest(keyword=keyword):
                    self.assertEqual(str(subject), parse_qs(urlsplit(BPS_CATEGORIES[keyword]).query)["subject"][0])

    def test_older_releases_are_searched_by_keyword_and_remain_relevant(self):
        unrelated = {"data": [{}, [{"title": "Inflasi", "abstract": "Kelompok pendidikan naik"}]]}
        relevant = {"data": [{}, [{"title": "Indeks Pembangunan Manusia", "abstract": "Nilai resmi fixture", "rl_date": "2025-01-01"}]]}
        with patch("bps_api._request_bps", side_effect=[unrelated, relevant]) as request:
            result = bps_api.cari_data_bps("saya ingin data IPM sulut")
        self.assertEqual(result["naratif"], "Nilai resmi fixture")
        self.assertEqual(request.call_args.kwargs, {"keyword": "indeks pembangunan manusia"})
        with patch("bps_api._request_bps", return_value=unrelated):
            self.assertIsNone(bps_api.cari_data_bps("pendidikan"))

    def test_unmapped_topic_reaches_official_retrieval_from_chat(self):
        phone = "6281234567890"
        main.session_mgr.set_step(phone, "rule_based_tanya_data")
        with patch("main.cari_data_bps", return_value=None), patch("main.cari_tabel_terbaru_bps", return_value=[
            {"title": "Produksi Kopra", "url": "https://sulut.bps.go.id/id/statistics-table/2/example/kopra.html"}
        ]) as search:
            result = main.handle_incoming_message(phone, "kopra")
        self.assertIn("Produksi Kopra", result["message"])
        search.assert_called_once_with("kopra", subject_url=None, limit=2)

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
        self.assertNotIn("cache", result["message"])
        self.assertNotIn("Cuplikan", result["message"])
        self.assertNotIn(official["link_pdf"], result["message"])
        self.assertEqual(sum(m["role"] == "user" for m in main.session_mgr.get_history(phone)), 1)

    def test_topic_response_keeps_two_table_links_without_api_source_or_unavailable_claim(self):
        phone = "6281234567890"
        tables = [{"title": "Indikator A", "date": "2026-09-01", "url": "https://sulut.bps.go.id/id/statistics-table/2/a/a.html"},
                  {"title": "Indikator B", "date": "2026-08-01", "url": "https://sulut.bps.go.id/id/statistics-table/2/b/b.html"}]
        main.session_mgr.set_step(phone, "rule_based_tanya_data")
        with patch("main.cari_data_bps", return_value=None), patch("main.cari_tabel_terbaru_bps", return_value=tables) as search:
            result = main.handle_incoming_message(phone, "pendidikan")
        search.assert_called_once_with("pendidikan", subject_url="https://sulut.bps.go.id/id/statistics-table?subject=521", limit=2)
        self.assertEqual(result["message"].count("https://"), 2)
        self.assertNotIn("belum tersedia dari API", result["message"])
        self.assertNotIn("Sumber BPS:", result["message"])
        self.assertLess(result["message"].index("Indikator A"), result["message"].index("Indikator B"))
        self.assertEqual(main.session_mgr.get_or_create(phone)["step"], "tanya_kepuasan")


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
