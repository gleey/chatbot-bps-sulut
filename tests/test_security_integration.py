"""Webhook, dashboard and provider integration using Flask and mocked HTTP."""
import hashlib
import hmac
import json
import os
import sys
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests import support  # noqa: F401
import db
import main
import message_queue
import operator_auth
import wa_webhook as web
from werkzeug.security import generate_password_hash

PHONE = "6281234567890"
PASSWORD = "synthetic-test-password"
PASSWORD_HASH = generate_password_hash(PASSWORD, method="pbkdf2:sha256:1000")


def payload(messages=None):
    return {"entry": [{"changes": [{"value": {"messages": messages or [
        {"id": "wamid.test", "from": PHONE, "type": "text", "text": {"body": "halo"}}
    ]}}]}]}


class WebIntegration(unittest.TestCase):
    def setUp(self):
        db.init_db()
        db.reset_db()
        operator_auth._attempts.clear()
        self.auth = patch.multiple(operator_auth, OPERATOR_USERNAME="petugas",
                                   OPERATOR_PASSWORD_HASH=PASSWORD_HASH,
                                   FLASK_SECRET_KEY="synthetic-session-secret")
        self.auth.start()
        self.addCleanup(self.auth.stop)
        web.app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
        self.client = web.app.test_client()

    def signed_post(self, data=None, raw=None, signature=None):
        raw = raw if raw is not None else json.dumps(data if data is not None else payload()).encode()
        signature = signature if signature is not None else "sha256=" + hmac.new(
            web.META_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        return self.client.post("/webhook", data=raw, content_type="application/json",
                                headers={"X-Hub-Signature-256": signature})

    def login(self):
        self.assertEqual(self.client.get("/operator/login").status_code, 200)
        with self.client.session_transaction() as state:
            csrf = state["csrf"]
        response = self.client.post("/operator/login", data={"username": "petugas", "password": PASSWORD, "csrf_token": csrf})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as state:
            self.csrf = state["csrf"]
        self.assertNotEqual(csrf, self.csrf)

    def operator_post(self, path, data):
        return self.client.post(path, json=data, headers={"X-CSRF-Token": self.csrf})

    def activate_operator(self):
        main.session_mgr.get_or_create(PHONE)
        main.session_mgr.set_step(PHONE, "operator")

    def test_get_verification(self):
        response = self.client.get("/webhook", query_string={"hub.mode": "subscribe", "hub.verify_token": web.META_VERIFY_TOKEN, "hub.challenge": "12345"})
        self.assertEqual((response.status_code, response.text), (200, "12345"))
        self.assertEqual(self.client.get("/webhook", query_string={"hub.mode": "subscribe", "hub.verify_token": "wrong"}).status_code, 403)

    def test_get_empty_secret_rejected(self):
        with patch.object(web, "META_VERIFY_TOKEN", ""):
            self.assertEqual(self.client.get("/webhook?hub.mode=subscribe&hub.verify_token=&hub.challenge=1").status_code, 403)

    def test_signature_accepts_exact_raw_bytes(self):
        raw = json.dumps(payload(), indent=3).encode()
        self.assertEqual(self.signed_post(raw=raw).status_code, 200)

    def test_signature_rejects_invalid_missing_and_modified_payload(self):
        raw = json.dumps(payload()).encode()
        valid = "sha256=" + hmac.new(web.META_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        for body, signature in [(raw, ""), (raw, "sha256=invalid"), (raw + b" ", valid), (raw, "sha256=é")]:
            with self.subTest(signature=signature):
                self.assertEqual(self.signed_post(raw=body, signature=signature).status_code, 403)
        with patch.object(web, "META_APP_SECRET", ""):
            self.assertEqual(self.signed_post(raw=raw).status_code, 403)

    def test_duplicate_delivery_runs_fsm_once(self):
        self.assertEqual(self.signed_post().json["accepted"], 1)
        self.assertEqual(self.signed_post().json["accepted"], 0)
        with patch.object(web, "_dispatch_reply", return_value=True) as send:
            self.assertTrue(message_queue.process_next(main.handle_incoming_message, send))
            self.assertFalse(message_queue.process_next(main.handle_incoming_message, send))
            self.assertEqual(send.call_count, 1)
        self.assertEqual(main.session_mgr.get_or_create(PHONE)["step"], "pilih_layanan")

    def test_all_batch_changes_and_messages_processed(self):
        data = payload()
        second = {"id": "id2", "from": PHONE, "type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"title": "Konsultasi"}}}
        data["entry"][0]["changes"].append({"value": {"messages": [second]}})
        data["entry"].append({"changes": [{"value": {"messages": [dict(second, id="id3")]}}]})
        self.assertEqual(self.signed_post(data).json["accepted"], 3)
        with patch("main.is_offline_mode", return_value=True), patch("main.cari_data_bps", return_value=None), patch("main.cari_tabel_terbaru_bps", return_value=[]):
            for _ in range(3):
                self.assertTrue(message_queue.process_next(main.handle_incoming_message, Mock(return_value=True)))

    def test_status_notifications_do_not_enter_fsm(self):
        response = self.signed_post({"entry": [{"changes": [{"value": {"statuses": [{"status": "delivered"}]}}]}]})
        self.assertEqual(response.json["accepted"], 0)

    def test_malformed_payloads_rejected_without_exception_details(self):
        for data in [[], {"entry": "wrong"}, {"entry": [None]}, payload([{"id": "x", "type": "text", "from": "<script>", "text": {"body": "hi"}}]), payload([{"id": "x", "from": PHONE, "type": "text", "text": []}])]:
            with self.subTest(data=data):
                self.assertEqual(self.signed_post(data).status_code, 400)

    def test_payload_size_limit(self):
        response = self.signed_post(raw=b"x" * (256 * 1024 + 1))
        self.assertEqual(response.status_code, 413)

    def test_rate_limit_returns_retryable_error(self):
        self.signed_post()
        data = payload()
        data["entry"][0]["changes"][0]["value"]["messages"][0]["id"] = "another"
        response = self.signed_post(data)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "2")

    def test_queue_capacity(self):
        with patch.object(message_queue, "MAX_PENDING", 0):
            self.assertEqual(self.signed_post().status_code, 503)

    def test_fonnte_json_form_and_separate_auth(self):
        with patch.object(web, "WHATSAPP_PROVIDER", "fonnte"):
            for content in ["json", "form"]:
                data = {"sender": PHONE, "message": "halo", "inboxid": "fonnte-test"}
                kwargs = {"json": data} if content == "json" else {"data": data}
                self.assertEqual(self.client.post("/webhook", **kwargs).status_code, 401)
                response = self.client.post("/webhook", **kwargs, headers={"Authorization": web.FONNTE_WEBHOOK_SECRET})
                self.assertEqual(response.status_code, 200)
            self.assertEqual(self.signed_post().status_code, 401)
        self.assertEqual(self.client.post("/webhook", json=data, headers={"Authorization": web.FONNTE_WEBHOOK_SECRET}).status_code, 403)

    def test_fonnte_missing_secret_never_authenticates(self):
        with patch.object(web, "WHATSAPP_PROVIDER", "fonnte"), patch.object(web, "FONNTE_WEBHOOK_SECRET", ""):
            self.assertEqual(self.client.post("/webhook", json={"sender": PHONE, "message": "hi"}).status_code, 401)

    def test_unauthenticated_operator_routes(self):
        self.assertEqual(self.client.get("/operator").status_code, 302)
        for path in ["/api/operator/sessions", "/stats"]:
            self.assertEqual(self.client.get(path).status_code, 401)
        for path in ["/api/operator/send", "/api/operator/close", "/operator/selesai", "/operator/logout"]:
            self.assertEqual(self.client.post(path, json={"phone": PHONE}, headers={"X-API-Key": "dev_operator_key_123"}).status_code, 401)

    def test_missing_operator_credentials_fail_closed(self):
        with patch.object(operator_auth, "OPERATOR_PASSWORD_HASH", ""):
            self.assertEqual(self.client.get("/operator").status_code, 503)

    def test_login_requires_csrf_and_correct_password(self):
        self.assertEqual(self.client.post("/operator/login", data={"username": "petugas", "password": PASSWORD}).status_code, 403)
        self.client.get("/operator/login")
        with self.client.session_transaction() as state:
            csrf = state["csrf"]
        self.assertEqual(self.client.post("/operator/login", data={"username": "petugas", "password": "wrong", "csrf_token": csrf}).status_code, 401)
        self.login()
        self.assertEqual(self.client.get("/api/operator/sessions").status_code, 200)

    def test_login_throttled(self):
        self.client.get("/operator/login")
        with self.client.session_transaction() as state:
            csrf = state["csrf"]
        statuses = [self.client.post("/operator/login", data={"username": "petugas", "password": "wrong", "csrf_token": csrf}).status_code for _ in range(6)]
        self.assertEqual(statuses, [401] * 5 + [429])

    def test_authenticated_wrong_identity_and_expiry_rejected(self):
        self.login()
        with self.client.session_transaction() as state:
            state["operator"] = "unauthorized"
        self.assertEqual(self.client.get("/api/operator/sessions").status_code, 401)
        self.login()
        with self.client.session_transaction() as state:
            state["login_at"] = time.time() - operator_auth.LOGIN_TTL - 1
        self.assertEqual(self.client.get("/api/operator/sessions").status_code, 401)

    def test_csrf_forgery_blocks_every_mutation(self):
        self.login()
        for path in ["/api/operator/send", "/api/operator/close", "/operator/selesai", "/operator/logout"]:
            self.assertEqual(self.client.post(path, json={"phone": PHONE}, headers={"X-CSRF-Token": "forged"}).status_code, 403)

    def test_dashboard_headers_and_safe_rendering(self):
        self.login()
        self.activate_operator()
        attack = '<img src=x onerror="alert(1)">\n<script>alert(1)</script>'
        main.session_mgr.add_to_history(PHONE, "user", attack)
        response = self.client.get("/operator")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(attack, response.text)
        self.assertIn("body.textContent = m.text", response.text)
        self.assertNotIn("onclick=", response.text)
        self.assertIn("script-src 'self' 'nonce-", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(self.client.get("/api/operator/sessions").json["sessions"][0]["messages"][0]["text"], attack)

    def test_operator_input_validation_and_active_session_required(self):
        self.login()
        for data in [[], {}, {"phone": "<script>", "message": "hello"}, {"phone": PHONE, "message": "x" * 4097}, {"phone": PHONE, "message": 123}, {"phone": PHONE, "message": "  "}]:
            self.assertEqual(self.operator_post("/api/operator/send", data).status_code, 400)
        self.assertEqual(self.operator_post("/api/operator/send", {"phone": PHONE, "message": "hello"}).status_code, 409)

    def test_send_failure_not_recorded_as_success_and_close_keeps_session(self):
        self.login()
        self.activate_operator()
        with patch.object(web, "_dispatch_reply", return_value=False):
            self.assertEqual(self.operator_post("/api/operator/send", {"phone": PHONE, "message": "hello"}).status_code, 502)
            self.assertEqual(self.operator_post("/api/operator/close", {"phone": PHONE}).status_code, 502)
        self.assertTrue(main.session_mgr.is_operator(PHONE))
        self.assertEqual(main.session_mgr.get_history(PHONE), [])

    def test_operator_send_close_and_archive(self):
        self.login()
        self.activate_operator()
        with patch.object(web, "_dispatch_reply", return_value=True):
            self.assertEqual(self.operator_post("/api/operator/send", {"phone": PHONE, "message": "hello"}).status_code, 200)
            self.assertEqual(self.operator_post("/operator/selesai", {"phone": PHONE}).status_code, 200)
        self.assertFalse(main.session_mgr.is_operator(PHONE))
        self.assertEqual(main.session_mgr.get_archives(PHONE)[0]["kind"], "pengaduan")
        self.assertEqual(main.session_mgr.get_archives(PHONE)[0]["close_reason"], "operator_closed")

    def test_close_refuses_pending_incoming_messages(self):
        self.login()
        self.activate_operator()
        self.signed_post()
        self.assertEqual(self.operator_post("/api/operator/close", {"phone": PHONE}).status_code, 409)

    def test_logout_revokes_browser_session(self):
        self.login()
        self.assertEqual(self.operator_post("/operator/logout", {}).status_code, 302)
        self.assertEqual(self.client.get("/api/operator/sessions").status_code, 401)

    def test_secure_cookie_configuration(self):
        with patch.dict(web.app.config, SESSION_COOKIE_SECURE=True):
            response = self.client.get("/operator/login")
            cookie = response.headers["Set-Cookie"]
            for attribute in ["Secure", "HttpOnly", "SameSite=Strict"]:
                self.assertIn(attribute, cookie)

    def test_health_checks_database(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        import sqlite3
        with patch.object(web, "get_conn", side_effect=sqlite3.OperationalError("synthetic")):
            self.assertEqual(self.client.get("/health").status_code, 503)

    def test_full_webhook_consultation_and_complaint_roundtrip(self):
        from llm_engine import set_offline_mode
        set_offline_mode(True)
        self.login()
        sent = Mock(return_value=True)

        def incoming(text, event_id):
            with db.get_conn() as conn:
                conn.execute("UPDATE webhook_inbox SET created_at=created_at-3")
            body = payload([{"id": event_id, "from": PHONE, "type": "text", "text": {"body": text}}])
            self.assertEqual(self.signed_post(body).status_code, 200)
            self.assertTrue(message_queue.process_next(main.handle_incoming_message, sent))

        with patch("main.is_jam_kerja", return_value=True), patch("main.cari_data_bps", return_value=None), patch("main.cari_tabel_terbaru_bps", return_value=[]):
            for index, text in enumerate(["halo", "Konsultasi", "inflasi", "Ya", "Selesai", "halo", "Pengaduan", "Saya perlu bantuan"]):
                incoming(text, f"roundtrip-{index}")
        sessions = self.client.get("/api/operator/sessions").json["sessions"]
        self.assertEqual(sessions[0]["messages"][-1]["text"], "Saya perlu bantuan")
        # Seven replies: the final complaint message is handed to the operator silently.
        self.assertEqual(sent.call_count, 7)
        with patch.object(web, "_dispatch_reply", return_value=True):
            self.assertEqual(self.operator_post("/api/operator/send", {"phone": PHONE, "message": "Kami bantu"}).status_code, 200)
            self.assertEqual(self.operator_post("/api/operator/close", {"phone": PHONE}).status_code, 200)
        self.assertEqual(self.client.get("/api/operator/sessions").json["sessions"], [])
        self.assertEqual(len(main.session_mgr.get_archives(PHONE)), 2)

    def test_wsgi_factory_initializes_workers_once(self):
        with patch.object(web, "_background_started", False), patch.object(web.config, "validate_startup"), patch.object(message_queue, "start_worker") as worker, patch.object(web, "start_prewarm_thread") as prewarm, patch.object(web, "start_session_timeout_thread") as timeout:
            self.assertIs(web.create_app(), web.app)
            self.assertIs(web.create_app(), web.app)
            worker.assert_called_once()
            prewarm.assert_called_once()
            timeout.assert_called_once()


class ProviderTests(unittest.TestCase):
    @patch("wa_webhook.requests.post")
    def test_meta_and_fonnte_response_validation(self, post):
        post.return_value.json.return_value = {"messages": [{"id": "synthetic"}]}
        self.assertTrue(web.send_wa_message(PHONE, "hi"))
        self.assertIn("timeout", post.call_args.kwargs)
        post.return_value.json.return_value = {"error": {"message": "failed"}}
        self.assertFalse(web.send_wa_message(PHONE, "hi"))
        for malformed in [{"messages": "queued"}, {"messages": [{}]}]:
            post.return_value.json.return_value = malformed
            self.assertFalse(web.send_wa_message(PHONE, "hi"))
        post.return_value.json.return_value = {"status": False}
        self.assertFalse(web.send_fonnte_message(PHONE, "hi"))
        post.return_value.json.return_value = {"status": True}
        self.assertTrue(web.send_fonnte_message(PHONE, "hi"))

    @patch("wa_webhook.requests.post")
    def test_provider_timeout_and_invalid_json(self, post):
        import requests
        for error in [requests.Timeout("synthetic"), ValueError("invalid json")]:
            post.side_effect = error
            self.assertFalse(web.send_wa_message(PHONE, "hi"))
            self.assertFalse(web.send_fonnte_message(PHONE, "hi"))

    def test_long_reply_chunks_and_does_not_hide_failure(self):
        with patch.object(web, "send_wa_message", return_value=True) as send, patch.object(web, "send_wa_interactive_button", return_value=True) as buttons:
            self.assertTrue(web._dispatch_reply(PHONE, {"message": "x" * 5000, "buttons": [{"id": "yes", "title": "Ya"}]}))
            self.assertEqual([len(call.args[1]) for call in send.call_args_list], [4096, 904])
            self.assertEqual(buttons.call_count, 1)
        with patch.object(web, "send_wa_message", return_value=False):
            self.assertFalse(web._dispatch_reply(PHONE, {"message": "hello"}))
