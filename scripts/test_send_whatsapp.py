#!/usr/bin/env python3
"""Quick test: send a real WhatsApp message via Meta Cloud API."""
import sys, json
try:
    import httpx
except ImportError:
    import subprocess; subprocess.run([sys.executable, "-m", "pip", "install", "httpx", "-q"])
    import httpx

TOKEN          = "EAGBZBscOZAxxkBRdaD05EjwLhQUZCLOIpCuKsj20CmuV1TbkctyhwM49Mx0y11YQNJoLZAyUAa2XCZAqDQA7US2oQESnoIbopHZBZCMZBunhOFE99SdtpsOAP0coWUozXQLjy05zWcTmJlJtGMlgVWgY3AMcahZBwlGGW5VZBHp3Cl4ZAagEWA3pgm1W5ryvhHNkAZDZD"
PHONE_NUM_ID   = "1028797620327128"
TO             = "201006854893"

url = f"https://graph.facebook.com/v20.0/{PHONE_NUM_ID}/messages"
payload = {
    "messaging_product": "whatsapp",
    "to": TO,
    "type": "text",
    "text": {"body": "✅ TMASI CRM — WhatsApp connection confirmed!"}
}

print(f"Sending to +{TO} via phone number ID {PHONE_NUM_ID}...")
try:
    r = httpx.post(url, json=payload, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=15)
    data = r.json()
    if r.status_code == 200:
        msg_id = data.get("messages", [{}])[0].get("id", "?")
        print(f"✅ SUCCESS — Message ID: {msg_id}")
        print("   Check your WhatsApp now!")
    else:
        print(f"❌ FAILED ({r.status_code})")
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f"❌ ERROR: {e}")
