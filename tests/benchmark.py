"""Reproducible local benchmark. All external APIs are mocked; no real messages."""
import hashlib
import hmac
import importlib.metadata
import json
import logging
import math
import os
import platform
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from tests import support  # noqa: F401
import bps_api
import db
import llm_engine
import main
import wa_webhook as web

SAMPLES = 50
PHONE = "6281234567890"


def summarize(samples):
    ordered = sorted(samples)
    return {"n": len(samples), "mean_ms": statistics.mean(samples),
            "median_ms": statistics.median(samples), "p95_ms": ordered[math.ceil(len(samples) * 0.95) - 1],
            "max_ms": max(samples), "samples_ms": samples}


def measure(action, prepare=lambda: None):
    samples = []
    for _ in range(SAMPLES):
        prepare()
        start = time.perf_counter_ns()
        action()
        samples.append((time.perf_counter_ns() - start) / 1_000_000)
    return summarize(samples)


def run():
    logging.disable(logging.CRITICAL)
    db.init_db()
    db.reset_db()
    results = {}

    def menu():
        assert main.handle_incoming_message(PHONE, "halo")["buttons"][0]["title"] == "Pengaduan"

    results["menu_fsm"] = measure(menu, lambda: main.session_mgr.reset(PHONE))

    with patch("llm_engine.genai.Client") as client, patch("main.cari_data_bps", return_value=None), patch("main.cari_tabel_terbaru_bps", return_value=[]):
        client.return_value.models.generate_content.return_value = Mock(text='{"intent":"cari_data","tujuan":"inflasi"}')

        def prepare_ai():
            llm_engine.set_offline_mode(False)
            main.session_mgr.reset(PHONE)
            main.session_mgr.set_step(PHONE, "gemini_tanya_data")

        def consult():
            assert "katalog" in main.handle_incoming_message(PHONE, "inflasi")["message"].lower()

        results["gemini_consultation_mocked"] = measure(consult, prepare_ai)

    endpoint = "list/model/statictable/domain/7100/page/1"
    fixture = {"status": "OK", "data": [{"page": 1}, [{"title": "Inflasi fixture"}]]}
    with patch("bps_api.requests.get", return_value=Mock(json=Mock(return_value=fixture))) as get:
        def clear_cache():
            conn = db.get_conn()
            try:
                conn.execute("DELETE FROM bps_cache")
                conn.commit()
            finally:
                conn.close()

        def retrieve():
            assert bps_api._request_bps(endpoint) == fixture

        results["bps_cache_miss_mocked_http"] = measure(retrieve, clear_cache)
        calls = get.call_count
        results["bps_cache_hit_sqlite"] = measure(retrieve)
        assert get.call_count == calls

    def prepare_takeover():
        main.session_mgr.reset(PHONE)
        main.session_mgr.set_step(PHONE, "pilih_layanan")

    with patch("main.is_jam_kerja", return_value=True):
        def takeover():
            main.handle_incoming_message(PHONE, "Pengaduan")
            assert main.session_mgr.is_operator(PHONE)

        results["operator_takeover_fsm"] = measure(takeover, prepare_takeover)

    db.reset_db()
    web.app.config["TESTING"] = True

    def concurrent_request(index):
        body = json.dumps({"entry": [{"changes": [{"value": {"messages": [{
            "id": f"benchmark-{index}", "from": f"6281000{index:06d}", "type": "text", "text": {"body": "halo"}
        }]}}]}]}).encode()
        signature = "sha256=" + hmac.new(web.META_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
        with web.app.test_client() as client:
            start = time.perf_counter_ns()
            response = client.post("/webhook", data=body, content_type="application/json", headers={"X-Hub-Signature-256": signature})
            elapsed = (time.perf_counter_ns() - start) / 1_000_000
            assert response.status_code == 200 and response.json["accepted"] == 1
            return elapsed

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results["webhook_ack_concurrent_8_threads"] = summarize(list(pool.map(concurrent_request, range(SAMPLES))))
    results["webhook_ack_concurrent_8_threads"]["batch_seconds"] = time.perf_counter() - start
    return {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": platform.python_version(), "os": platform.system(), "kernel": platform.release(),
                        "cpu_count_reported": os.cpu_count(), "database": "temporary SQLite WAL",
                        "packages": {name: importlib.metadata.version(name) for name in ["Flask", "google-genai", "requests", "waitress"]}},
        "method": "50 samples per scenario; setup excluded; p95 nearest-rank; no warm-up; APIs mocked without artificial latency; Flask test client (no TCP/Waitress).",
        "limits": "Local processing and ACK only. No Gemini/BPS network time, WhatsApp delivery, queue wait under live traffic, or 3-second end-to-end proof.",
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
