import re

with open("wa_webhook.py", "r") as f:
    content = f.read()

# 1. Insert send_wa_interactive_button after send_wa_message
interactive_func = '''
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

'''
content = re.sub(r'(@app\.route\("/webhook", methods=\["GET", "POST"\]\))', interactive_func + r'\1', content)


# 2. Modify payload parsing to support interactive messages
parsing_old = '''                        # Handle text message
                        if message_obj.get("type") == "text":
                            message_text = message_obj["text"]["body"]
                        else:
                            message_text = "" # Ignore non-text for now

                        if sender and message_text:
                            print(f"\\nPesan Masuk dari [{sender}]: {message_text}")
                            balasan = handle_incoming_message(sender, message_text)
                            
                            if balasan is None:
                                print(f"Diteruskan ke operator: {sender}")
                            else:
                                send_wa_message(sender, balasan["message"])'''

parsing_new = '''                        message_type = message_obj.get("type")
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
                            print(f"\\nPesan Masuk dari [{sender}]: {message_text}")
                            balasan = handle_incoming_message(sender, message_text)
                            
                            if balasan is None:
                                print(f"Diteruskan ke operator: {sender}")
                            else:
                                if "buttons" in balasan and balasan["buttons"]:
                                    send_wa_interactive_button(sender, balasan["message"], balasan["buttons"])
                                else:
                                    send_wa_message(sender, balasan["message"])'''

content = content.replace(parsing_old, parsing_new)

with open("wa_webhook.py", "w") as f:
    f.write(content)
print("Webhook patched successfully!")
