#!/usr/bin/env python3
"""
TMASI CRM - WhatsApp Webhook Test Script
Tests inbound webhook payloads for all 5 configured WhatsApp lines.
Usage: python scripts/test_whatsapp_webhook.py [--base-url http://localhost:8000]
"""

import argparse
import json
import sys
import time
import requests
from datetime import datetime

def make_text_payload(phone_number_id, from_id, text, ts=None):
    ts = ts or str(int(time.time()))
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WABA_ID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "TEST",
                        "phone_number_id": phone_number_id
                    },
                    "contacts": [{"profile": {"name": f"Test User {from_id[-4:]}"}, "wa_id": from_id}],
                    "messages": [{
                        "from": from_id,
                        "id": f"wamid.test_{phone_number_id}_{ts}",
                        "timestamp": ts,
                        "text": {"body": text},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }

def make_image_payload(phone_number_id, from_id, media_id="fake_media_id_12345"):
    ts = str(int(time.time()))
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WABA_ID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "TEST", "phone_number_id": phone_number_id},
                    "contacts": [{"profile": {"name": "Test Image Sender"}, "wa_id": from_id}],
                    "messages": [{
                        "from": from_id,
                        "id": f"wamid.test_img_{ts}",
                        "timestamp": ts,
                        "image": {
                            "caption": "Test image upload",
                            "mime_type": "image/jpeg",
                            "sha256": "fakehash",
                            "id": media_id
                        },
                        "type": "image"
                    }]
                },
                "field": "messages"
            }]
        }]
    }

def main():
    parser = argparse.ArgumentParser(description="Test TMASI CRM WhatsApp webhook")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the running app")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    webhook_url = f"{base_url}/api/whatsapp/webhook"
    
    print(f"Testing TMASI CRM WhatsApp Webhook")
    print(f"Target: {webhook_url}")
    print("=" * 60)

    # Check health first
    try:
        health = requests.get(f"{base_url}/api/health", timeout=5).json()
        print(f"Health: {health.get('status')} | DB: {health.get('database')}")
    except Exception as e:
        print(f"ERROR: Cannot reach {base_url} - {e}")
        sys.exit(1)

    # Get configured lines
    try:
        lines_resp = requests.get(f"{base_url}/api/crm/whatsapp-lines", timeout=5)
        lines = lines_resp.json()
        print(f"\nConfigured WhatsApp lines: {len(lines)}")
        for l in lines:
            print(f"  [{l.get('short_code','??')}] {l.get('label','?')} - {l.get('display_phone_number','?')}")
    except Exception as e:
        print(f"WARNING: Could not fetch lines: {e}")
        lines = []

    # Get phone_number_ids from environment or use defaults
    import os
    from dotenv import load_dotenv
    load_dotenv()

    line_ids = [
        os.environ.get("WHATSAPP_LINE_1_ID", "international-care"),
        os.environ.get("WHATSAPP_LINE_2_ID", "bookings"),
        os.environ.get("WHATSAPP_LINE_3_ID", "emergency-desk"),
        os.environ.get("WHATSAPP_LINE_4_ID", "arabic-support"),
        os.environ.get("WHATSAPP_LINE_5_ID", "follow-up-care"),
    ]

    from_ids = [
        "201001111111",
        "201002222222",
        "201003333333",
        "201004444444",
        "201005555555",
    ]

    messages = [
        "Hello, I need a consultation",
        "I would like to book an appointment",
        "This is an emergency",
        "مرحباً، أريد الاستفسار عن الخدمات",
        "Following up on my previous appointment",
    ]

    print("\n--- Testing text messages for each line ---")
    results = []
    for i, (line_id, from_id, msg_text) in enumerate(zip(line_ids, from_ids, messages)):
        payload = make_text_payload(line_id, from_id, msg_text)
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            ok = resp.status_code == 200
            results.append(ok)
            print(f"  Line {i+1} ({line_id[:20]}): {'✓ OK' if ok else f'✗ FAILED ({resp.status_code})'}")
            if args.verbose:
                print(f"    Response: {resp.text[:100]}")
        except Exception as e:
            results.append(False)
            print(f"  Line {i+1}: ✗ ERROR - {e}")

    print("\n--- Testing image payload ---")
    img_payload = make_image_payload(line_ids[0], "201009999999")
    try:
        resp = requests.post(webhook_url, json=img_payload, timeout=10)
        ok = resp.status_code == 200
        results.append(ok)
        print(f"  Image message: {'✓ OK' if ok else f'✗ FAILED ({resp.status_code})'}")
    except Exception as e:
        results.append(False)
        print(f"  Image message: ✗ ERROR - {e}")

    time.sleep(1)  # Allow processing

    print("\n--- Verifying conversations were created ---")
    try:
        # Login to get token
        login_resp = requests.post(f"{base_url}/api/auth/login", json={"username": os.environ.get("BOOTSTRAP_ADMIN_USERNAME","admin"), "password": os.environ.get("BOOTSTRAP_ADMIN_PASSWORD","admin123")}, timeout=5)
        token = login_resp.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}

        for line_id, from_id in zip(line_ids, from_ids):
            conv_resp = requests.get(f"{base_url}/api/whatsapp/conversations?limit=100", headers=headers, timeout=5)
            convs = conv_resp.json().get("items", [])
            found = any(c.get("customer_whatsapp_id") == from_id for c in convs)
            print(f"  Conversation for {from_id}: {'✓ Found' if found else '✗ Not found'}")
            results.append(found)
    except Exception as e:
        print(f"  Verification error: {e}")

    passed = sum(results)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed")
    if passed == total:
        print("✓ All webhook tests passed!")
    else:
        print(f"✗ {total - passed} tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
