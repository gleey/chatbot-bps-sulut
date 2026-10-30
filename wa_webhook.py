"""
WhatsApp Webhook Server — Meta Cloud API + Fonnte.
Dengan logging terstruktur, validasi input, rate limiting, dan health check.
"""
import logging
import hashlib
import hmac
import sqlite3
import os
import threading
import time
import requests
from flask import Flask, request, jsonify, render_template

from logging_setup import setup_logging
from main import handle_incoming_message, session_mgr
from llm_engine import is_offline_mode
from bps_api import start_prewarm_thread
import config
import message_queue
from db import get_conn
from operator_auth import install_auth
from config import (
    META_ACCESS_TOKEN, META_PHONE_NUMBER_ID, META_VERIFY_TOKEN,
    WHATSAPP_PROVIDER, FONNTE_TOKEN, META_APP_SECRET, META_API_VERSION, FONNTE_WEBHOOK_SECRET,
)
from webhook_utils import validate_message, check_rate_limit, valid_phone, phone_lock

setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
install_auth(app)




# ============================================================
# Kirim pesan — Meta Cloud API
# ============================================================
def _meta_accepted(payload):
    messages = payload.get("messages") if isinstance(payload, dict) else None
    return isinstance(messages, list) and bool(messages) and all(
        isinstance(message, dict) and isinstance(message.get("id"), str) and bool(message["id"])
        for message in messages)


def send_wa_message(target, message):
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID or not META_API_VERSION:
        logger.error("META_ACCESS_TOKEN atau META_PHONE_NUMBER_ID belum di-set!")
        return False

    url = f"https://graph.facebook.com/{META_API_VERSION}/{META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": target,
        "type": "text",
        "text": {"body": message},
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        return _meta_accepted(result)
    except (requests.exceptions.RequestException, ValueError) as e:
        logger.warning("Pengiriman Meta gagal (%s)", type(e).__name__)
        return False


def send_wa_interactive_button(target, text_body, buttons):
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID or not META_API_VERSION:
        logger.error("META_ACCESS_TOKEN atau META_PHONE_NUMBER_ID belum di-set!")
        return False

    url = f"https://graph.facebook.com/{META_API_VERSION}/{META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    action_buttons = [
        {"type": "reply", "reply": {"id": btn["id"], "title": btn["title"]}}
        for btn in buttons
    ]

    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": target,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text_body},
            "action": {"buttons": action_buttons},
        },
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        return _meta_accepted(result)
    except (requests.exceptions.RequestException, ValueError) as e:
        logger.warning("Pengiriman tombol Meta gagal (%s)", type(e).__name__)
        return False


# ============================================================
# Kirim pesan — Fonnte API
# ============================================================
def send_fonnte_message(target, message):
    if not FONNTE_TOKEN:
        logger.error("FONNTE_TOKEN belum di-set!")
        return False

    url = "https://api.fonnte.com/send"
    headers = {"Authorization": FONNTE_TOKEN}
    data = {"target": target, "message": message}

    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        return isinstance(result, dict) and result.get("status") is True
    except (requests.exceptions.RequestException, ValueError) as e:
        logger.warning("Pengiriman Fonnte gagal (%s)", type(e).__name__)
        return False


def send_fonnte_interactive_button(target, text_body, buttons):
    """Fonnte tidak support native button — fallback ke teks."""
    fallback_text = text_body + "\n\nSilakan ketik pilihan Anda:\n"
    for i, btn in enumerate(buttons, start=1):
        fallback_text += f"{i}. {btn['title']}\n"
    return send_fonnte_message(target, fallback_text.strip())


# ============================================================
# Helper: kirim balasan sesuai provider
# ============================================================
WA_INTERACTIVE_BODY_MAX = 1024


def _dispatch_reply(sender, balasan):
    """Kirim balasan ke sender sesuai provider yang dikonfigurasi."""
    if balasan is None:
        return True
    msg = balasan["message"]
    buttons = balasan.get("buttons")
    send_text = send_fonnte_message if WHATSAPP_PROVIDER == "fonnte" else send_wa_message
    if buttons and WHATSAPP_PROVIDER == "meta" and len(msg) <= WA_INTERACTIVE_BODY_MAX:
        return send_wa_interactive_button(sender, msg, buttons)
    # Teks terlalu panjang untuk interactive button body (max 1024).
    # Kirim teks utama dulu, lalu tombol terpisah.
    for offset in range(0, len(msg), 4096):
        if not send_text(sender, msg[offset:offset + 4096]):
            return False
    if buttons:
        if WHATSAPP_PROVIDER == "fonnte":
            return send_fonnte_interactive_button(sender, "Silakan pilih:", buttons)
        return send_wa_interactive_button(sender, "Silakan pilih:", buttons)
    return True


# ============================================================
# Webhook endpoint
# ============================================================
def _meta_events(data):
    if not isinstance(data.get("entry"), list):
        raise ValueError("entry harus berupa array")
    events = []
    for entry in data["entry"]:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                kind = message.get("type")
                if kind == "text":
                    text = message.get("text", {}).get("body")
                elif kind == "interactive":
                    interactive = message.get("interactive", {})
                    reply = interactive.get(interactive.get("type"), {})
                    text = reply.get("title")
                else:
                    continue
                event_id, phone = message.get("id"), message.get("from")
                clean, error = validate_message(text)
                if not isinstance(event_id, str) or not event_id or len(event_id) > 256 or not valid_phone(phone) or error:
                    raise ValueError("Pesan tidak valid")
                events.append(("meta:" + event_id, phone, clean))
    return events


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token", "")
        challenge = request.args.get("hub.challenge")
        if (WHATSAPP_PROVIDER == "meta" and META_VERIFY_TOKEN and mode == "subscribe"
                and hmac.compare_digest(token.encode(), META_VERIFY_TOKEN.encode()) and challenge):
            return challenge, 200
        return "Forbidden", 403

    raw = request.get_data(cache=True)
    # 1. Fonnte payload
    if WHATSAPP_PROVIDER == "fonnte":
        # Validasi header Authorization dari Fonnte
        supplied = request.headers.get("Authorization", "")
        if not FONNTE_WEBHOOK_SECRET or not hmac.compare_digest(supplied.encode(), FONNTE_WEBHOOK_SECRET.encode()):
            return jsonify(status="error", message="Unauthorized"), 401
    else:
        # 2. Meta payload: verify the exact bytes received, before parsing JSON.
        signature = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(META_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not META_APP_SECRET or not hmac.compare_digest(signature.encode(), expected.encode()):
            return jsonify(status="error", message="Forbidden"), 403
    try:
        data = request.get_json(silent=True) if request.is_json else request.form.to_dict()
        if not isinstance(data, dict) or not data:
            return jsonify(status="error", message="Payload tidak valid"), 400
        if WHATSAPP_PROVIDER == "fonnte":
            sender, text = data.get("sender"), data.get("message")
            clean, error = validate_message(text)
            event_id = data.get("inboxid") or data.get("id")
            if not valid_phone(sender) or error or not isinstance(event_id, (str, int)) or not str(event_id) or len(str(event_id)) > 256:
                return jsonify(status="error", message="sender, message, inboxid wajib valid"), 400
            events = [("fonnte:" + str(event_id), sender, clean)]
        else:
            events = _meta_events(data)
        if len(events) > 100:
            return jsonify(status="error", message="Batch melebihi 100 pesan"), 400
        accepted = message_queue.enqueue(events)
        return jsonify(status="ok", accepted=accepted), 200
    except message_queue.RateLimited:
        return jsonify(status="error", message="Rate limited"), 429, {"Retry-After": "2"}
    except message_queue.InboxFull:
        return jsonify(status="error", message="Inbox penuh"), 503, {"Retry-After": "5"}
    except (ValueError, TypeError, AttributeError, KeyError):
        return jsonify(status="error", message="Struktur payload tidak valid"), 400
    except sqlite3.Error:
        logger.error("Database inbox tidak tersedia")
        return jsonify(status="error", message="Layanan sementara tidak tersedia"), 503


def _process_message(sender, message_text):
    """Validasi, rate limit, proses, reply."""
    if not valid_phone(sender):
        return False

    clean_text, error = validate_message(message_text)
    if error:
        logger.warning("Pesan invalid dari %s: %s", sender, error)
        return

    if not check_rate_limit(sender):
        logger.info("Rate limited: %s", sender)
        return

    logger.info("Pesan masuk tervalidasi")
    balasan = handle_incoming_message(sender, clean_text)
    _dispatch_reply(sender, balasan)


# ============================================================
# Operator Web Dashboard & API Endpoints
# ============================================================
@app.route("/operator", methods=["GET"])
def operator_dashboard():
    """Render Web UI Dashboard Operator."""
    return render_template("operator.html")


@app.route("/api/operator/sessions", methods=["GET"])
def api_operator_sessions():
    """Ambil daftar semua sesi pengaduan aktif yang sedang ditangani operator."""
    sessions = session_mgr.get_operator_sessions()
    return jsonify({"status": "ok", "sessions": sessions})


@app.route("/api/operator/send", methods=["POST"])
def api_operator_send():
    """Kirim balasan dari petugas operator ke WhatsApp pengguna."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(status="error", message="JSON object wajib diisi"), 400
    nomor, pesan = data.get("phone"), data.get("message")
    if not valid_phone(nomor) or not isinstance(pesan, str) or not pesan.strip() or len(pesan) > 4096:
        return jsonify(status="error", message="Nomor atau pesan tidak valid (maksimal 4096 karakter)"), 400
    with phone_lock(nomor):
        if not session_mgr.is_operator(nomor):
            return jsonify(status="error", message="Sesi operator tidak aktif"), 409
        # Simpan balasan operator ke riwayat percakapan
        # Kirim ke WhatsApp pengguna
        if not _dispatch_reply(nomor, {"message": pesan.strip()}):
            return jsonify(status="error", message="Pengiriman gagal atau belum dapat dipastikan; periksa provider sebelum mengulang"), 502
        session_mgr.add_to_history(nomor, "operator", pesan.strip())
        session_mgr.touch(nomor)
    return jsonify(status="ok", message="Pesan diterima provider")


@app.route("/api/operator/close", methods=["POST"])
def api_operator_close():
    """Selesaikan sesi operator dan aktifkan kembali bot untuk user ini."""
    data = request.get_json(silent=True)
    nomor = data.get("phone") if isinstance(data, dict) else None
    if not valid_phone(nomor):
        return jsonify(status="error", message="Nomor tidak valid"), 400
    with phone_lock(nomor):
        if not session_mgr.is_operator(nomor):
            return jsonify(status="error", message="Sesi operator tidak aktif"), 409
        if message_queue.pending_for(nomor):
            return jsonify(status="error", message="Pesan masuk masih diproses; muat ulang sebelum menutup sesi"), 409
        # Kirim pesan penutup ke pengguna
        pesan_penutup = (
            "Terima kasih telah menghubungi petugas BPS Sulawesi Utara.\n"
            "Sesi pengaduan telah selesai. Jika masih membutuhkan bantuan, Bot BPS siap membantu kembali.")
        if not _dispatch_reply(nomor, {"message": pesan_penutup}):
            return jsonify(status="error", message="Pesan penutup gagal atau belum dapat dipastikan; sesi tetap aktif"), 502
        session_mgr.add_to_history(nomor, "operator", pesan_penutup)
        # Reset sesi agar bot aktif kembali
        session_mgr.reset(nomor, reason="operator_closed")
    return jsonify(status="ok", message="Pengaduan diarsipkan dan bot kembali aktif")


@app.route("/operator/selesai", methods=["POST"])
def operator_selesai():
    # Authentication check
    # Authentication and CSRF are enforced by the same session guard as every operator API.
    return api_operator_close()


# ============================================================
# Health check & stats
# ============================================================
@app.route("/health", methods=["GET"])
def health():
    try:
        conn = get_conn()
        try:
            conn.execute("SELECT 1 FROM sessions LIMIT 1").fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return jsonify(status="error", message="Database unavailable"), 503
    return jsonify(status="ok", mode="offline" if is_offline_mode() else "ai",
                   worker_running=message_queue.worker_running())


@app.route("/stats", methods=["GET"])
def stats():
    return jsonify({
        "active_sessions": session_mgr.count_active(),
        "ai_mode": not is_offline_mode(),
    })


SESSION_CLOSING_MSG = (
    "Sesi layanan BPS ditutup otomatis karena tidak ada aktivitas. "
    "Silakan kirim pesan baru jika Anda memerlukan bantuan pencarian data statistik. Terima kasih!"
)


def start_session_timeout_thread(check_interval=15):
    """Background thread: Cek sesi expired tiap N detik & kirim pesan penutup otomatis."""
    def _loop():
        while True:
            try:
                expired_phones = session_mgr.get_expired_sessions()
                for phone in expired_phones:
                    with phone_lock(phone):
                        if phone not in session_mgr.get_expired_sessions() or message_queue.pending_for(phone):
                            continue
                        logger.info("Session expired")
                        _dispatch_reply(phone, {"message": SESSION_CLOSING_MSG})
                        session_mgr.reset(phone, reason="timeout")
            except Exception as e:
                logger.error("Session timeout worker gagal (%s)", type(e).__name__)
            time.sleep(check_interval)

    t = threading.Thread(target=_loop, daemon=True, name="SessionTimeoutThread")
    t.start()
    return t


# ============================================================
# Main
# ============================================================
_background_started = False
_background_lock = threading.Lock()


def start_background_workers():
    global _background_started
    with _background_lock:
        if _background_started:
            return
        config.validate_startup()
        message_queue.start_worker(handle_incoming_message, _dispatch_reply)
        # Jalankan background pre-warming cache BPS (tiap 6 jam)
        start_prewarm_thread(interval_hours=6)
        # Jalankan background timeout checker sesi (tiap 15 detik)
        start_session_timeout_thread(check_interval=15)
        _background_started = True


def create_app():
    """WSGI factory: exactly one application process must own background workers."""
    start_background_workers()
    return app


def run_server():
    from waitress import serve
    start_background_workers()
    logger.info("WhatsApp webhook ready (provider=%s)", WHATSAPP_PROVIDER)
    # Jalankan dengan Waitress (WSGI server produksi) jika tersedia, fallback ke app.run()
    # Waitress is a required dependency; a missing install must not start a development server in production.
    serve(app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), threads=4)


if __name__ == "__main__":
    run_server()
