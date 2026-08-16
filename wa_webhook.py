"""
WhatsApp Webhook Server — Meta Cloud API + Fonnte.
Dengan logging terstruktur, validasi input, rate limiting, dan health check.
"""
import logging
import os
import threading
import time
import requests
from flask import Flask, request, jsonify, render_template

from logging_setup import setup_logging
from main import handle_incoming_message, session_mgr
from llm_engine import is_offline_mode
from bps_api import start_prewarm_thread
from config import (
    META_ACCESS_TOKEN, META_PHONE_NUMBER_ID, META_VERIFY_TOKEN,
    WHATSAPP_PROVIDER, FONNTE_TOKEN,
)
from webhook_utils import validate_message, check_rate_limit

setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

META_API_VERSION = os.getenv("META_API_VERSION", "v19.0")
OPERATOR_API_KEY = os.getenv("OPERATOR_API_KEY", "dev_operator_key_123")


# ============================================================
# Kirim pesan — Meta Cloud API
# ============================================================
def send_wa_message(target, message):
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
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
        logger.info("Balasan terkirim ke %s", target)
        return True
    except requests.exceptions.RequestException as e:
        logger.error("Gagal mengirim balasan ke %s: %s", target, e)
        if hasattr(e, "response") and e.response is not None:
            logger.error("Detail: %s", e.response.text)
        return False


def send_wa_interactive_button(target, text_body, buttons):
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
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
        logger.info("Tombol interaktif terkirim ke %s", target)
        return True
    except requests.exceptions.RequestException as e:
        logger.error("Gagal mengirim tombol ke %s: %s", target, e)
        if hasattr(e, "response") and e.response is not None:
            logger.error("Detail: %s", e.response.text)
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
        logger.info("[Fonnte] Balasan terkirim ke %s", target)
        return True
    except requests.exceptions.RequestException as e:
        logger.error("[Fonnte] Gagal mengirim balasan ke %s: %s", target, e)
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
        logger.info("Diteruskan ke operator: %s", sender)
        return

    msg = balasan["message"]
    has_buttons = balasan.get("buttons")

    if WHATSAPP_PROVIDER == "fonnte":
        if has_buttons:
            send_fonnte_interactive_button(sender, msg, has_buttons)
        else:
            send_fonnte_message(sender, msg)
    else:
        if has_buttons:
            if len(msg) > WA_INTERACTIVE_BODY_MAX:
                # Teks terlalu panjang untuk interactive button body (max 1024).
                # Kirim teks utama dulu, lalu tombol terpisah.
                send_wa_message(sender, msg)
                send_wa_interactive_button(
                    sender, "Silakan pilih:", has_buttons
                )
            else:
                send_wa_interactive_button(sender, msg, has_buttons)
        else:
            send_wa_message(sender, msg)


# ============================================================
# Webhook endpoint
# ============================================================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if not mode or not token:
            return "Forbidden", 403

        if mode == "subscribe" and token == META_VERIFY_TOKEN:
            logger.info("WEBHOOK_VERIFIED")
            return challenge, 200
            
        return "Forbidden", 403

    try:
        data = request.json or request.form
        if not data:
            return jsonify({"status": "error", "message": "No payload"}), 400

        # 1. Fonnte payload
        if WHATSAPP_PROVIDER == "fonnte" and "sender" in data and "message" in data:
            # Validasi header Authorization dari Fonnte
            auth_header = request.headers.get("Authorization")
            if auth_header != FONNTE_TOKEN:
                logger.warning("Fonnte webhook unauthenticated")
                return jsonify({"status": "error", "message": "Unauthorized"}), 401
                
            sender = data.get("sender")
            message_text = data.get("message")
            _process_message(sender, message_text)
            return jsonify({"status": "ok"}), 200

        # 2. Meta payload
        if "entry" in data and len(data["entry"]) > 0:
            # skipped request verification via X-Hub-Signature-256 for now (local/demo scope)
            for entry in data["entry"]:
                if "changes" not in entry or not entry["changes"]:
                    continue
                change = entry["changes"][0]
                if "value" not in change or "messages" not in change["value"]:
                    continue

                message_obj = change["value"]["messages"][0]
                sender = message_obj.get("from")

                message_type = message_obj.get("type")
                message_text = ""

                if message_type == "text":
                    message_text = message_obj["text"]["body"]
                elif message_type == "interactive":
                    interactive_obj = message_obj["interactive"]
                    if interactive_obj["type"] == "button_reply":
                        message_text = interactive_obj["button_reply"]["title"]
                    elif interactive_obj["type"] == "list_reply":
                        message_text = interactive_obj["list_reply"]["title"]

                threading.Thread(target=_process_message, args=(sender, message_text), daemon=True).start()

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.exception("Error webhook: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


def _process_message(sender, message_text):
    """Validasi, rate limit, proses, reply."""
    if not sender:
        return

    clean_text, error = validate_message(message_text)
    if error:
        logger.warning("Pesan invalid dari %s: %s", sender, error)
        return

    if not check_rate_limit(sender):
        logger.info("Rate limited: %s", sender)
        return

    logger.info("Pesan masuk dari [%s]: %s", sender, clean_text[:100])
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
    data = request.json or {}
    nomor = data.get("phone")
    pesan = data.get("message")

    if not nomor or not pesan:
        return jsonify({"status": "error", "message": "phone dan message wajib diisi"}), 400

    # Simpan balasan operator ke riwayat percakapan
    session_mgr.add_to_history(nomor, "operator", pesan)
    session_mgr.touch(nomor)

    # Kirim ke WhatsApp pengguna
    berhasil = False
    if WHATSAPP_PROVIDER == "fonnte":
        berhasil = send_fonnte_message(nomor, pesan)
    else:
        berhasil = send_wa_message(nomor, pesan)

    if berhasil:
        return jsonify({"status": "ok", "message": "Pesan berhasil terkirim"})
    return jsonify({"status": "error", "message": "Gagal mengirim pesan ke WhatsApp"}), 500


@app.route("/api/operator/close", methods=["POST"])
def api_operator_close():
    """Selesaikan sesi operator dan aktifkan kembali bot untuk user ini."""
    data = request.json or {}
    nomor = data.get("phone")

    if not nomor:
        return jsonify({"status": "error", "message": "phone wajib diisi"}), 400

    # Kirim pesan penutup ke pengguna
    pesan_penutup = (
        "Terima kasih telah menghubungi petugas BPS Sulawesi Utara.\n"
        "Sesi pengaduan telah selesai. Jika masih membutuhkan bantuan, saya (Bot BPS) siap membantu kembali."
    )
    if WHATSAPP_PROVIDER == "fonnte":
        send_fonnte_message(nomor, pesan_penutup)
    else:
        send_wa_message(nomor, pesan_penutup)

    # Reset sesi agar bot aktif kembali
    session_mgr.reset(nomor)

    return jsonify({"status": "ok", "message": "Sesi diakhiri dan bot kembali aktif"})


@app.route("/operator/selesai", methods=["POST"])
def operator_selesai():
    # Authentication check
    api_key = request.headers.get("X-API-Key")
    if api_key != OPERATOR_API_KEY:
        logger.warning("Unauthorized access to /operator/selesai")
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
    data = request.json
    if not data or not data.get("phone"):
        return jsonify({"status": "error", "message": "phone required"}), 400

    nomor = data["phone"]
    session_mgr.active_bot(nomor)

    pesan = "Terima kasih telah menghubungi petugas BPS.\nJika masih membutuhkan bantuan, saya siap membantu kembali."
    _dispatch_reply(nomor, {"message": pesan})

    return jsonify({
        "status": "ok",
        "message": "Sesi user diakhiri dan status bot diaktifkan kembali",
    })


# ============================================================
# Health check & stats
# ============================================================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "mode": "offline" if is_offline_mode() else "ai",
    })


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
                    logger.info("Session expired (5 min inactivity): %s", phone)
                    _dispatch_reply(phone, {"message": SESSION_CLOSING_MSG})
                    session_mgr.reset(phone)
            except Exception as e:
                logger.error("Error dalam session timeout thread: %s", e)
            time.sleep(check_interval)

    t = threading.Thread(target=_loop, daemon=True, name="SessionTimeoutThread")
    t.start()
    return t


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("WhatsApp Webhook Server Berjalan")
    logger.info("Provider: %s", WHATSAPP_PROVIDER)
    logger.info("=" * 50)

    # Jalankan background pre-warming cache BPS (tiap 6 jam)
    start_prewarm_thread(interval_hours=6)
    # Jalankan background timeout checker sesi (tiap 15 detik)
    start_session_timeout_thread(check_interval=15)

    # Jalankan dengan Waitress (WSGI server produksi) jika tersedia, fallback ke app.run()
    try:
        from waitress import serve
        logger.info("Serving WSGI app di http://0.0.0.0:5000 (Waitress)")
        logger.info("Dashboard Operator tersedia di: http://localhost:5000/operator")
        serve(app, host="0.0.0.0", port=5000)
    except ImportError:
        is_debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
        app.run(host="0.0.0.0", port=5000, debug=is_debug)
