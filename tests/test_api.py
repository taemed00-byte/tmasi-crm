"""TMASI CRM API Tests"""
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_tmasi.db")
os.environ.setdefault("BOOTSTRAP_ADMIN_USERNAME", "admin")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "admin123")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.main import app
from app.database import engine, Base
from app.startup import run_startup

Base.metadata.create_all(bind=engine)
run_startup()

client = TestClient(app)

def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_login():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()

def test_login_bad():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401

def get_token():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    return resp.json()["access_token"]

def auth():
    return {"Authorization": f"Bearer {get_token()}"}

def test_whatsapp_lines():
    resp = client.get("/api/whatsapp/lines", headers=auth())
    assert resp.status_code == 200
    lines = resp.json()
    assert len(lines) >= 5

def test_crm_whatsapp_lines():
    resp = client.get("/api/crm/whatsapp-lines")
    assert resp.status_code == 200
    assert len(resp.json()) >= 5

def test_webhook_verify():
    resp = client.get("/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=hcig_virtual_care_verify_token&hub.challenge=testchallenge")
    assert resp.status_code == 200
    assert resp.text == "testchallenge"

def test_webhook_verify_bad_token():
    resp = client.get("/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=test")
    assert resp.status_code == 403

def test_webhook_inbound_message():
    import time
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"id": "waba", "changes": [{"value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "test", "phone_number_id": "international-care"},
            "contacts": [{"profile": {"name": "Test Patient"}, "wa_id": "201001234567"}],
            "messages": [{"from": "201001234567", "id": f"wamid_test_{int(time.time())}", "timestamp": str(int(time.time())), "text": {"body": "Hello from test"}, "type": "text"}]
        }, "field": "messages"}]}]
    }
    resp = client.post("/api/whatsapp/webhook", json=payload)
    assert resp.status_code == 200

def test_conversations():
    resp = client.get("/api/whatsapp/conversations?limit=10", headers=auth())
    assert resp.status_code == 200
    assert "items" in resp.json()

def test_patients_list():
    resp = client.get("/api/patients?limit=10", headers=auth())
    assert resp.status_code == 200
    assert "items" in resp.json()

def test_create_patient():
    resp = client.post("/api/patients", json={
        "name": "Test Patient API",
        "phone": "+20 100 0000000",
        "country": "Egypt",
        "service_type": "Test",
    }, headers=auth())
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Patient API"
    return data["id"]

def test_doctors_list():
    resp = client.get("/api/doctors", headers=auth())
    assert resp.status_code == 200

def test_clinics_list():
    resp = client.get("/api/clinics", headers=auth())
    assert resp.status_code == 200

def test_users_list():
    resp = client.get("/api/users", headers=auth())
    assert resp.status_code == 200

def test_index_html():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "TMASI CRM" in resp.text

def teardown_module(module):
    """Clean up test database."""
    try:
        os.remove("./test_tmasi.db")
    except FileNotFoundError:
        pass
