#!/usr/bin/env python3
"""
TMASI CRM - Render Deployment Verification Script
Polls production URL, verifies health, WhatsApp lines, and UI layout.
Usage: python scripts/verify_render_deploy.py --url https://YOUR_APP.onrender.com
"""

import argparse
import sys
import time
import json
import requests
import os

def poll_until_ready(base_url, max_wait=300, interval=10):
    print(f"Polling {base_url}/api/health until ready (max {max_wait}s)...")
    elapsed = 0
    while elapsed < max_wait:
        try:
            resp = requests.get(f"{base_url}/api/health", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                print(f"  ✓ App is up! Status: {data.get('status')}, DB: {data.get('database')}")
                return data
        except Exception as e:
            print(f"  [{elapsed}s] Not ready: {e}")
        time.sleep(interval)
        elapsed += interval
    print("  ✗ App did not become ready in time")
    sys.exit(1)

def verify_whatsapp_lines(base_url):
    print("\n[Check] WhatsApp lines...")
    resp = requests.get(f"{base_url}/api/crm/whatsapp-lines", timeout=10)
    if resp.status_code != 200:
        print(f"  ✗ /api/crm/whatsapp-lines returned {resp.status_code}")
        return False
    lines = resp.json()
    if len(lines) < 5:
        print(f"  ✗ Expected 5 lines, got {len(lines)}")
        return False
    for l in lines:
        print(f"  ✓ [{l.get('short_code','??')}] {l.get('label','?')}")
    return True

def login(base_url):
    username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "admin")
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "admin123")
    resp = requests.post(f"{base_url}/api/auth/login", json={"username": username, "password": password}, timeout=10)
    if resp.status_code == 200:
        token = resp.json().get("access_token")
        print(f"  ✓ Login successful as '{username}'")
        return token
    print(f"  ✗ Login failed: {resp.status_code} {resp.text}")
    return None

def verify_conversations(base_url, token):
    print("\n[Check] Conversations API...")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{base_url}/api/whatsapp/conversations?limit=10", headers=headers, timeout=10)
    if resp.status_code == 200:
        total = resp.json().get("total", 0)
        print(f"  ✓ Conversations endpoint OK ({total} total)")
        return True
    print(f"  ✗ Conversations endpoint: {resp.status_code}")
    return False

def verify_static(base_url):
    print("\n[Check] Static files...")
    checks = ["/static/style.css", "/static/app.js"]
    ok = True
    for path in checks:
        resp = requests.get(f"{base_url}{path}", timeout=10)
        if resp.status_code == 200:
            print(f"  ✓ {path} ({len(resp.content)} bytes)")
        else:
            print(f"  ✗ {path}: {resp.status_code}")
            ok = False
    return ok

def send_test_webhook(base_url, phone_number_id, from_id, text):
    ts = str(int(time.time()))
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA_ID", "changes": [{"value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "TEST", "phone_number_id": phone_number_id},
            "contacts": [{"profile": {"name": "Verify Test"}, "wa_id": from_id}],
            "messages": [{"from": from_id, "id": f"wamid.verify_{ts}", "timestamp": ts, "text": {"body": text}, "type": "text"}]
        }, "field": "messages"}]}]
    }
    resp = requests.post(f"{base_url}/api/whatsapp/webhook", json=payload, timeout=10)
    return resp.status_code == 200

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Production Render URL")
    parser.add_argument("--wait", type=int, default=300, help="Max seconds to wait for startup")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    results = {}

    print("=" * 60)
    print("TMASI CRM — Render Deployment Verification")
    print(f"URL: {base_url}")
    print("=" * 60)

    # 1. Health check
    health = poll_until_ready(base_url, max_wait=args.wait)
    results["health"] = health.get("status") == "ok"

    # 2. WhatsApp lines
    results["whatsapp_lines"] = verify_whatsapp_lines(base_url)

    # 3. Login
    print("\n[Check] Authentication...")
    token = login(base_url)
    results["login"] = token is not None

    if token:
        # 4. Conversations API
        results["conversations_api"] = verify_conversations(base_url, token)

        # 5. Webhook test
        print("\n[Check] Webhook processing...")
        lines_resp = requests.get(f"{base_url}/api/crm/whatsapp-lines", timeout=10).json()
        if lines_resp:
            phone_number_id = lines_resp[0].get("display_phone_number", "test-line-1")
            # Get the actual phone_number_id from a fresh lines list
            lines_detail = requests.get(f"{base_url}/api/whatsapp/lines", headers={"Authorization": f"Bearer {token}"}, timeout=10).json()
            if lines_detail:
                pid = lines_detail[0].get("phone_number_id", "international-care")
                ok = send_test_webhook(base_url, pid, "201099887766", "Production verification test")
                print(f"  {'✓' if ok else '✗'} Webhook test payload")
                results["webhook"] = ok

    # 6. Static files
    results["static_files"] = verify_static(base_url)

    # 7. Index HTML
    print("\n[Check] Index page...")
    resp = requests.get(f"{base_url}/", timeout=10)
    has_crm = "TMASI CRM" in resp.text
    print(f"  {'✓' if has_crm else '✗'} Index page {'contains' if has_crm else 'missing'} TMASI CRM")
    results["index_html"] = has_crm

    # Summary
    print("\n" + "=" * 60)
    print("Verification Summary:")
    all_pass = True
    for check, passed in results.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check.replace('_', ' ').title()}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print("✓ All checks passed! Production deployment is healthy.")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"✗ {len(failed)} check(s) failed: {', '.join(failed)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
