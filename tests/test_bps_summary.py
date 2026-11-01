"""Official table detail summaries: dimensions, periods, missing values and chat integration."""
import unittest
from unittest.mock import patch

from tests import support  # noqa: F401
import bps_api
import db
import main


def table(source="3", **values):
    return {"id": "example", "title": "Indikator Pendidikan", "tablesource": source,
            "latest_period": 2025, "url": "https://sulut.bps.go.id/id/statistics-table/3/example/table.html",
            **values}


def yearbook(**values):
    return {"status": "OK", "data": [{}, {
        "tahun_data": 2025,
        "kolom": {"school": {"nama_variabel": "Persentase Masih Sekolah"}},
        "data": [
            {"label_raw": "Laki-laki - 7-12", "variables": {"school": {"value": "99,24"}}},
            {"label_raw": "Laki-laki+Perempuan 7-23", "variables": {"school": {"value": "73,34"}}},
        ], **values,
    }]}


def dynamic(**values):
    return {"status": "OK", "var": [{"val": 1781, "label": "APK Perguruan Tinggi", "unit": "Tidak Ada Satuan"}],
            "vervar": [{"val": 7100, "label": "Provinsi Sulawesi Utara"}],
            "turvar": [{"val": "0", "label": "Tidak ada"}],
            "tahun": [{"val": 125, "label": "2025"}], "turtahun": [{"val": 0, "label": "Tahun"}],
            "datacontent": {"7100178101250": 33.51}, **values}


class TableSummaryTests(unittest.TestCase):
    def setUp(self):
        db.init_db()
        db.reset_db()

    def test_yearbook_preserves_aggregate_group_year_indicator_and_unit(self):
        with patch("bps_api._request_bps", return_value=yearbook()) as request:
            summary = bps_api.ringkas_tabel_bps(table(), "pendidikan")
        self.assertTrue(summary.startswith("• 2025 — Laki-laki+Perempuan 7-23"))
        self.assertIn("Persentase Masih Sekolah: 73,34 persen", summary)
        self.assertNotIn("2026", summary)
        request.assert_called_once_with("view/domain/7100/model/tablestatistic/id/example/lang/ind", year=2025)

    def test_yearbook_keeps_missing_values_distinct_from_zero(self):
        rows = [{"label": "Sulawesi Utara", "variables": {
            "missing": {"value": "NA"}, "dots": {"value": "..."},
            "dash": {"value": "–"}, "zero": {"value": "0,00"}, "flag": {"value": "12,50*"},
        }}]
        payload = yearbook(kolom={name: {"nama_variabel": name} for name in rows[0]["variables"]}, data=rows)
        with patch("bps_api._request_bps", return_value=payload):
            summary = bps_api.ringkas_tabel_bps(table())
        self.assertIn("zero: 0,00", summary)
        self.assertIn("flag: 12,50*", summary)
        self.assertNotIn("missing:", summary)
        self.assertNotIn("dots:", summary)
        self.assertNotIn("dash:", summary)

    def test_requested_year_is_sent_and_mismatched_response_is_not_used(self):
        with patch("bps_api._request_bps", return_value=yearbook()) as request:
            self.assertEqual(bps_api.ringkas_tabel_bps(table(), "pendidikan 2024"), "")
            self.assertEqual(request.call_args.kwargs, {"year": "2024"})
        with patch("bps_api._request_bps", return_value=yearbook(tahun_data=2024)):
            self.assertIn("2024", bps_api.ringkas_tabel_bps(table(), "pendidikan 2024"))

    def test_dynamic_decodes_dimension_keys_without_inventing_a_unit(self):
        with patch("bps_api._request_bps", return_value=dynamic()):
            summary = bps_api.ringkas_tabel_bps(table("2"))
        self.assertIn("2025; Provinsi Sulawesi Utara: 33,51", summary)
        self.assertNotIn("persen", summary)
        self.assertNotIn("Tidak Ada Satuan", summary)

    def test_dynamic_selects_latest_populated_month_and_preserves_unit(self):
        payload = dynamic(
            var=[{"val": 1924, "label": "Bongkar Muat", "unit": "Ton"}],
            vervar=[{"val": 1, "label": "Bongkar"}, {"val": 2, "label": "Muat"}],
            tahun=[{"val": 126, "label": "2026"}],
            turtahun=[{"val": 7, "label": "Juli"}, {"val": 8, "label": "Agustus"}, {"val": 9, "label": "September"}],
            datacontent={"1192401267": 268766, "1192401268": 216523, "2192401268": 187077})
        with patch("bps_api._request_bps", return_value=payload):
            summary = bps_api.ringkas_tabel_bps(table("2", latest_period=2026))
        self.assertIn("2026; Agustus; Bongkar: 216.523 Ton", summary)
        self.assertIn("2026; Agustus; Muat: 187.077 Ton", summary)
        self.assertNotIn("September", summary)
        self.assertNotIn("Juli", summary)

    def test_dynamic_month_rows_select_latest_populated_month(self):
        payload = dynamic(
            vervar=[{"val": 1, "label": "Januari"}, {"val": 8, "label": "Agustus"}, {"val": 9, "label": "September"}],
            datacontent={"1178101250": 10, "8178101250": 20})
        with patch("bps_api._request_bps", return_value=payload):
            summary = bps_api.ringkas_tabel_bps(table("2"))
        self.assertTrue(summary.startswith("• 2025; Agustus: 20"))

    def test_month_row_order_does_not_depend_on_response_order(self):
        payload = dynamic(vervar=[{"val": 8, "label": "Agustus"}, {"val": 1, "label": "Januari"}],
                          datacontent={"1178101250": 10, "8178101250": 20})
        with patch("bps_api._request_bps", return_value=payload):
            self.assertTrue(bps_api.ringkas_tabel_bps(table("2")).startswith("• 2025; Agustus: 20"))

    def test_dynamic_prefers_province_total_and_rejects_wrong_year(self):
        payload = dynamic(vervar=[{"val": 1, "label": "Minahasa"}, {"val": 7100, "label": "Sulawesi Utara"}],
                          datacontent={"1178101250": 10, "7100178101250": 33.51})
        with patch("bps_api._request_bps", return_value=payload):
            self.assertTrue(bps_api.ringkas_tabel_bps(table("2")).startswith("• 2025; Sulawesi Utara: 33,51"))
            self.assertEqual(bps_api.ringkas_tabel_bps(table("2"), "2024"), "")

    def test_simple_static_table_keeps_header_year_and_row_label(self):
        payload = {"status": "OK", "data": {"table": "<table><tr><th>Aspek</th><th>2021</th><th>2022</th></tr>"
                   "<tr><td>Kebebasan</td><td>82,92</td><td>83,00</td></tr></table>"}}
        with patch("bps_api._request_bps", return_value=payload):
            self.assertIn("2022 — Kebebasan: 83,00", bps_api.ringkas_tabel_bps(table("1")))
            self.assertIn("2021 — Kebebasan: 82,92", bps_api.ringkas_tabel_bps(table("1"), "2021"))
            self.assertEqual(bps_api.ringkas_tabel_bps(table("1"), "2020"), "")

    def test_merged_static_headers_are_not_guessed(self):
        payload = {"status": "OK", "data": {"table": "<table><tr><th colspan='2'>2025</th></tr>"
                   "<tr><td>Minahasa</td><td>10</td></tr></table>"}}
        with patch("bps_api._request_bps", return_value=payload):
            self.assertEqual(bps_api.ringkas_tabel_bps(table("1")), "")

    def test_static_merged_title_does_not_hide_unmerged_year_headers(self):
        payload = {"status": "OK", "data": {"table": "<table><tr><td colspan='2'>Indeks Demokrasi 2021</td></tr>"
                   "<tr><th>Aspek</th><th>2021</th></tr><tr><td>Kebebasan</td><td>82,92</td></tr></table>"}}
        with patch("bps_api._request_bps", return_value=payload):
            self.assertIn("2021 — Kebebasan: 82,92", bps_api.ringkas_tabel_bps(table("1")))

    def test_static_counts_that_look_like_years_do_not_replace_period_headers(self):
        payload = {"status": "OK", "data": {"table": "<table><tr><th>Wilayah</th><th>2024</th><th>2025</th></tr>"
                   "<tr><td>Minahasa</td><td>2021</td><td>2022</td></tr>"
                   "<tr><td>Manado</td><td>10</td><td>20</td></tr></table>"}}
        with patch("bps_api._request_bps", return_value=payload):
            summary = bps_api.ringkas_tabel_bps(table("1"))
        self.assertIn("2025 — Minahasa: 2022", summary)
        self.assertIn("2025 — Manado: 20", summary)
        self.assertNotIn("2022 — Manado", summary)

    def test_yearbook_status_code_keeps_estimation_note_and_hides_missing(self):
        payload = yearbook(keterangan_data={"e": "Angka estimasi"}, data=[
            {"label": "Sulawesi Utara", "variables": {"school": {"value": "12,50", "value_code": "e"}}},
            {"label": "Minahasa", "variables": {"school": {"value": "0", "value_code": "NA"}}},
        ])
        with patch("bps_api._request_bps", return_value=payload):
            summary = bps_api.ringkas_tabel_bps(table())
        self.assertIn("12,50 (Angka estimasi)", summary)
        self.assertNotIn("Minahasa", summary)

    def test_invalid_and_unavailable_detail_returns_empty_summary(self):
        for payload in [None, [], {"data": None}, {"data": []}, {"data": [1, "invalid"]},
                        yearbook(kolom=[], data={}), dynamic(var="invalid"), dynamic(datacontent={})]:
            with self.subTest(payload=payload), patch("bps_api._request_bps", return_value=payload):
                self.assertEqual(bps_api.ringkas_tabel_bps(table()), "")
                self.assertEqual(bps_api.ringkas_tabel_bps(table("2")), "")

    def test_untrusted_table_identifier_never_becomes_a_request(self):
        with patch("bps_api._request_bps") as request:
            for value in [None, {}, table(id="../escape"), table(tablesource="9")]:
                self.assertEqual(bps_api.ringkas_tabel_bps(value), "")
            request.assert_not_called()

    @patch("bps_api.requests.get")
    def test_detail_cache_avoids_duplicate_http(self, get):
        get.return_value.json.return_value = yearbook()
        first = bps_api.ringkas_tabel_bps(table())
        self.assertTrue(first)
        self.assertEqual(first, bps_api.ringkas_tabel_bps(table()))
        self.assertEqual(get.call_count, 1)

    def test_education_chat_has_real_cells_and_two_table_links_without_a_release(self):
        rows = [table(title="Partisipasi Sekolah"), table("2", title="APK Perguruan Tinggi", id="second")]
        def response(endpoint, **params):
            return dynamic() if "/id/second/" in endpoint else yearbook()
        phone = "6281234567890"
        main.session_mgr.set_step(phone, "rule_based_tanya_data")
        with patch("main.cari_data_bps", return_value=None), patch("main.cari_tabel_terbaru_bps", return_value=rows), \
                patch("bps_api._request_bps", side_effect=response):
            answer = main.handle_incoming_message(phone, "Saya ingin data mengenai pendidikan")["message"]
        self.assertIn("73,34 persen", answer)
        self.assertIn("33,51", answer)
        self.assertIn("2025", answer)
        self.assertEqual(answer.count("https://"), 2)
        self.assertNotIn("Sumber BPS:", answer)
        self.assertNotIn("belum tersedia", answer)

    def test_detail_failure_keeps_links_and_explains_summary_failure(self):
        phone = "6281234567890"
        main.session_mgr.set_step(phone, "rule_based_tanya_data")
        with patch("main.cari_data_bps", return_value=None), patch("main.cari_tabel_terbaru_bps", return_value=[table()]), \
                patch("bps_api._request_bps", return_value=None):
            answer = main.handle_incoming_message(phone, "pendidikan")["message"]
        self.assertIn("Ringkasan angka belum dapat dibaca", answer)
        self.assertIn(table()["url"], answer)
        self.assertNotIn("0 persen", answer)

    def test_number_format_does_not_turn_missing_or_nonfinite_values_into_zero(self):
        for value in [None, "NA", "...", "–", "<script>12</script>", True, float("nan"), float("inf")]:
            self.assertEqual(bps_api._summary_number(value), "")
        self.assertEqual(bps_api._summary_number(0), "0")
        self.assertEqual(bps_api._summary_number(33.51), "33,51")


if __name__ == "__main__":
    unittest.main()
