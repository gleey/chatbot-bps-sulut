import requests
import json

payload = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "123456789",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "123",
                            "phone_number_id": "123"
                        },
                        "messages": [
                            {
                                "from": "081122334455",
                                "id": "wamid.12345",
                                "timestamp": "12345",
                                "type": "text",
                                "text": {
                                    "body": "halo"
                                }
                            }
                        ]
                    },
                    "field": "messages"
                }
            ]
        }
    ]
}

try:
    resp = requests.post("http://127.0.0.1:5000/webhook", json=payload)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"Error: {e}")
