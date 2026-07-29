import os
import requests
from flask import Flask, request, jsonify
from main import handle_incoming_message, session_mgr
from config import META_ACCESS_TOKEN, META_PHONE_NUMBER_ID, META_VERIFY_TOKEN, WHATSAPP_PROVIDER, FONNTE_TOKEN

app = Flask(__name__)

def send_wa_message(target, message):
    """Kirim balasan ke WhatsApp via Meta Cloud API."""
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
        print("META_ACCESS_TOKEN atau META_PHONE_NUMBER_ID belum di-set!")
        return False
        
    url = f"https://graph.facebook.com/v19.0/{META_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messaging_product": "whatsapp",
        "to": target,
        "type": "text",
        "text": {"body": message}
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"Balasan terkirim ke {target}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Gagal mengirim balasan ke {target}: {e}")
        if e.response is not None:
            print(f"Detail error: {e.response.text}")
        return False



def send_wa_interactive_button(target, text_body, buttons):
    """Kirim balasan berupa tombol interaktif ke WhatsApp."""
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
        print("META_ACCESS_TOKEN atau META_PHONE_NUMBER_ID belum di-set!")
        return False
        
    url = f"https://graph.facebook.com/v19.0/{META_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    action_buttons = []
    for btn in buttons:
        action_buttons.append({
            "type": "reply",
            "reply": {
                "id": btn["id"],
                "title": btn["title"]
            }
        })
    
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": target,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": text_body
            },
            "action": {
                "buttons": action_buttons
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"Tombol interaktif terkirim ke {target}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Gagal mengirim tombol ke {target}: {e}")
        if e.response is not None:
            print(f"Detail error: {e.response.text}")
        return False


def send_fonnte_message(target, message):
    """Kirim balasan ke WhatsApp via Fonnte API."""
    if not FONNTE_TOKEN:
        print("FONNTE_TOKEN belum di-set!")
        return False
        
    url = "https://api.fonnte.com/send"
    headers = {
        "Authorization": FONNTE_TOKEN
    }
    data = {
        "target": target,
        "message": message
    }
    
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        print(f"[Fonnte] Balasan terkirim ke {target}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"[Fonnte] Gagal mengirim balasan ke {target}: {e}")
        return False

def send_fonnte_interactive_button(target, text_body, buttons):
    """Kirim balasan tombol via Fonnte API (Fallback Teks jika belum support JSON tombol native)."""
    # Fallback sederhana untuk testing: menggabungkan text_body dengan pilihan tombol
    fallback_text = text_body + "\n\nSilakan ketik pilihan Anda:\n"
    for i, btn in enumerate(buttons, start=1):
        fallback_text += f"{i}. {btn['title']}\n"
        
    return send_fonnte_message(target, fallback_text.strip())

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    """Endpoint untuk menerima pesan webhook dari Meta."""
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode and token:
            if mode == "subscribe" and token == META_VERIFY_TOKEN:
                print("WEBHOOK_VERIFIED")
                return challenge, 200
            else:
                return "Forbidden", 403
        return "Webhook is active", 200

    try:
        # Fonnte usually sends form data or json
        data = request.json or request.form
        if not data:
            return jsonify({"status": "error", "message": "No payload"}), 400
            
        # 1. Parse payload Fonnte
        if WHATSAPP_PROVIDER == "fonnte" and "sender" in data and "message" in data:
            sender = data.get("sender")
            message_text = data.get("message")
            
            if sender and message_text:
                print(f"\nPesan Masuk dari [{sender}] (via Fonnte): {message_text}")
                balasan = handle_incoming_message(sender, message_text)
                
                if balasan is None:
                    print(f"Diteruskan ke operator: {sender}")
                else:
                    if "buttons" in balasan and balasan["buttons"]:
                        send_fonnte_interactive_button(sender, balasan["message"], balasan["buttons"])
                    else:
                        send_fonnte_message(sender, balasan["message"])
            return jsonify({"status": "ok"}), 200
            
        # 2. Parse payload Meta
        if "entry" in data and len(data["entry"]) > 0:
            for entry in data["entry"]:
                if "changes" in entry and len(entry["changes"]) > 0:
                    change = entry["changes"][0]
                    if "value" in change and "messages" in change["value"]:
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

                        if sender and message_text:
                            print(f"\nPesan Masuk dari [{sender}]: {message_text}")
                            balasan = handle_incoming_message(sender, message_text)
                            
                            if balasan is None:
                                print(f"Diteruskan ke operator: {sender}")
                            else:
                                if WHATSAPP_PROVIDER == "fonnte":
                                    if "buttons" in balasan and balasan["buttons"]:
                                        send_fonnte_interactive_button(sender, balasan["message"], balasan["buttons"])
                                    else:
                                        send_fonnte_message(sender, balasan["message"])
                                else:
                                    # Default ke Meta API
                                    if "buttons" in balasan and balasan["buttons"]:
                                        send_wa_interactive_button(sender, balasan["message"], balasan["buttons"])
                                    else:
                                        send_wa_message(sender, balasan["message"])
                                
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"Error webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/operator/selesai", methods=["POST"])
def operator_selesai():
    data = request.json
    nomor = data.get("phone")

    session_mgr.active_bot(nomor)

    pesan = "Terima kasih telah menghubungi petugas BPS.\nJika masih membutuhkan bantuan, saya siap membantu kembali 😊"
    if WHATSAPP_PROVIDER == "fonnte":
        send_fonnte_message(nomor, pesan)
    else:
        send_wa_message(nomor, pesan)

    return jsonify({
        "status": "ok",
        "message": "Sesi user diakhiri dan status bot diaktifkan kembali"
    })


if __name__ == "__main__":
    print("=" * 50)
    print("Meta WhatsApp Webhook Server Berjalan")
    print("=" * 50)
    print(f"Pastikan ngrok jalan: ngrok http 5000")
    print(f"Set Webhook URL di Meta Dashboard:")
    print(f"=> https://<ngrok-url>/webhook")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)
