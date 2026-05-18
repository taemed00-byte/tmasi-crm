#!/usr/bin/env python3
"""
TMASI CRM — Browser UI Layout Test
Tests critical layout invariants using headless Chrome via Playwright (if available)
or falls back to an API-based sanity check.
Usage: python scripts/browser_ui_test.py [--base-url http://localhost:8000]
"""

import argparse
import sys
import os
import time
import requests

def api_sanity_test(base_url):
    """API-based smoke test when Playwright is not available."""
    print("Running API-based sanity test...")

    username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "admin")
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "admin123")

    # 1. Health
    resp = requests.get(f"{base_url}/api/health", timeout=10)
    assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
    print(f"  ✓ Health: {resp.json().get('status')}")

    # 2. Login
    resp = requests.post(f"{base_url}/api/auth/login", json={"username": username, "password": password}, timeout=10)
    assert resp.status_code == 200, f"Login failed: {resp.status_code}"
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"  ✓ Login OK")

    # 3. WhatsApp lines
    resp = requests.get(f"{base_url}/api/whatsapp/lines", headers=headers, timeout=10)
    assert resp.status_code == 200
    lines = resp.json()
    assert len(lines) >= 5, f"Expected 5 WA lines, got {len(lines)}"
    print(f"  ✓ WhatsApp lines: {len(lines)}")
    for l in lines:
        print(f"    [{l['short_code']}] {l['label']} ({l['open_count']} open)")

    # 4. Conversations
    line_id = lines[0]["id"]
    resp = requests.get(f"{base_url}/api/whatsapp/conversations?line_id={line_id}&limit=5", headers=headers, timeout=10)
    assert resp.status_code == 200
    convs = resp.json().get("items", [])
    print(f"  ✓ Conversations for line 1: {len(convs)}")

    # 5. If there are conversations, check opening one
    if convs:
        conv_id = convs[0]["id"]
        resp = requests.get(f"{base_url}/api/whatsapp/conversations/{conv_id}", headers=headers, timeout=10)
        assert resp.status_code == 200
        conv = resp.json()
        print(f"  ✓ Opened conversation: {conv.get('customer_name') or conv.get('customer_whatsapp_id')}")
        print(f"    Messages: {len(conv.get('messages', []))}")
        print(f"    Has patient: {conv.get('patient_id') is not None}")

    # 6. Static files
    for path in ["/static/style.css", "/static/app.js", "/"]:
        resp = requests.get(f"{base_url}{path}", timeout=10)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"
    print(f"  ✓ Static files OK")

    # 7. Patients
    resp = requests.get(f"{base_url}/api/patients?limit=5", headers=headers, timeout=10)
    assert resp.status_code == 200
    print(f"  ✓ Patients API: {resp.json().get('total', 0)} total")

    print("\n✓ All API sanity tests passed!")
    return True

def playwright_test(base_url, username, password):
    """Full browser layout test using Playwright."""
    from playwright.sync_api import sync_playwright
    import re

    viewports = [
        {"width": 1920, "height": 1080, "name": "desktop-1920"},
        {"width": 2048, "height": 1228, "name": "desktop-2048"},
        {"width": 1366, "height": 768, "name": "laptop-1366"},
        {"width": 1180, "height": 760, "name": "narrow-1180"},
    ]

    screenshots_dir = "tests/screenshots"
    os.makedirs(screenshots_dir, exist_ok=True)

    all_passed = True

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for vp in viewports:
            print(f"\n  Testing viewport: {vp['name']} ({vp['width']}x{vp['height']})")
            page = browser.new_page(viewport={"width": vp["width"], "height": vp["height"]})

            try:
                # Login
                page.goto(f"{base_url}/", wait_until="networkidle")
                page.fill("#loginUsername", username)
                page.fill("#loginPassword", password)
                page.click(".btn-login")
                page.wait_for_selector("#app:not(.hidden)", timeout=10000)
                print(f"    ✓ Login successful")

                # Wait for WA lines
                page.wait_for_selector(".wa-line-btn", timeout=8000)
                rail_count = page.locator(".wa-line-btn").count()
                print(f"    ✓ WhatsApp rail: {rail_count} lines")
                assert rail_count >= 5, f"Expected 5 rail buttons, got {rail_count}"

                # Click first conversation
                page.wait_for_selector(".conv-item", timeout=8000)
                page.locator(".conv-item").first.click()
                time.sleep(1.5)

                # Verify caseDetail does NOT have empty-state
                case_classes = page.locator("#caseDetail").get_attribute("class") or ""
                has_empty = "empty-state" in case_classes
                if has_empty:
                    print(f"    ✗ FAIL: #caseDetail still has empty-state after conversation open!")
                    all_passed = False
                else:
                    print(f"    ✓ #caseDetail cleared empty-state")

                # Check all key elements visible
                checks = [
                    ("#sidebar", "Sidebar"),
                    ("#waRail", "WA Rail"),
                    ("#convList", "Conv List"),
                    ("#chatHeader", "Chat Header"),
                    ("#chatBody", "Chat Body"),
                    ("#chatComposer", "Composer"),
                    ("#patientDrawer", "Patient Drawer"),
                    ("#composerInput", "Composer Input"),
                ]
                for selector, label in checks:
                    el = page.locator(selector)
                    visible = el.is_visible()
                    if not visible:
                        print(f"    ✗ FAIL: {label} ({selector}) not visible!")
                        all_passed = False
                    else:
                        print(f"    ✓ {label} visible")

                # Check no horizontal overflow
                scroll_x = page.evaluate("window.scrollX")
                body_left = page.evaluate("document.body.scrollLeft")
                if scroll_x != 0 or body_left != 0:
                    print(f"    ✗ FAIL: Horizontal scroll: scrollX={scroll_x}, bodyLeft={body_left}")
                    all_passed = False
                else:
                    print(f"    ✓ No horizontal overflow")

                # Force horizontal scroll and verify it resets
                page.evaluate("window.scrollTo(900, window.scrollY)")
                time.sleep(0.8)
                scroll_x_after = page.evaluate("window.scrollX")
                if scroll_x_after > 10:
                    print(f"    ✗ FAIL: H-scroll reset failed: scrollX={scroll_x_after}")
                    all_passed = False
                else:
                    print(f"    ✓ Horizontal scroll auto-resets")

                # Check chat body has independent scroll
                overflow_y = page.evaluate("getComputedStyle(document.getElementById('chatBody')).overflowY")
                if overflow_y not in ("auto", "scroll"):
                    print(f"    ✗ FAIL: chatBody overflow-y is '{overflow_y}', expected auto/scroll")
                    all_passed = False
                else:
                    print(f"    ✓ Chat body overflow-y: {overflow_y}")

                # Screenshot
                shot_path = f"{screenshots_dir}/{vp['name']}.png"
                page.screenshot(path=shot_path, full_page=False)
                print(f"    ✓ Screenshot saved: {shot_path}")

            except Exception as e:
                print(f"    ✗ Error: {e}")
                all_passed = False
            finally:
                page.close()

        browser.close()

    return all_passed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--playwright", action="store_true", help="Use Playwright for browser tests")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "admin")
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "admin123")

    print("=" * 60)
    print("TMASI CRM — Browser UI Test")
    print(f"Target: {base_url}")
    print("=" * 60)

    if args.playwright:
        try:
            passed = playwright_test(base_url, username, password)
        except ImportError:
            print("Playwright not installed. Run: pip install playwright && playwright install chromium")
            print("Falling back to API sanity test...\n")
            passed = api_sanity_test(base_url)
    else:
        passed = api_sanity_test(base_url)

    if not passed:
        print("\n✗ UI tests FAILED")
        sys.exit(1)
    else:
        print("\n✓ UI tests PASSED")

if __name__ == "__main__":
    main()
