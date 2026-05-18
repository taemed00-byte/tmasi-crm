import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./tmasi_local.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "tmasi-crm-dev-secret-key-change-in-production")
BOOTSTRAP_ADMIN_USERNAME = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "admin")
BOOTSTRAP_ADMIN_PASSWORD = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "admin123")

WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "hcig_virtual_care_verify_token")
WHATSAPP_APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")
WHATSAPP_BUSINESS_ACCOUNT_ID = os.environ.get("WHATSAPP_BUSINESS_ACCOUNT_ID", "")

WHATSAPP_GRAPH_URL = "https://graph.facebook.com/v20.0"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12  # 12 hours

UPLOAD_DIR = "uploads"

# ─── Patient Portal ──────────────────────────────────────────────────────────
# Resend (https://resend.com) — free tier: 100 emails/day, no credit card
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
# Sender address — must be a verified domain in Resend (or "onboarding@resend.dev" for dev)
PORTAL_FROM_EMAIL = os.environ.get("PORTAL_FROM_EMAIL", "TMASI Medical Centre <onboarding@resend.dev>")
# Public base URL of this deployment (used in email links)
PORTAL_BASE_URL = os.environ.get("PORTAL_BASE_URL", "http://localhost:8000")

# WhatsApp line definitions from env
WA_LINE_DEFAULTS = [
    {
        "env_id_key": "WHATSAPP_LINE_1_ID",
        "env_label_key": "WHATSAPP_LINE_1_LABEL",
        "env_phone_key": "WHATSAPP_LINE_1_DISPLAY_PHONE",
        "internal_id": "international-care",
        "short_code": "IC",
        "default_label": "International Care",
        "default_phone": "+20 100 000 1001",
        "default_service": "International Care",
    },
    {
        "env_id_key": "WHATSAPP_LINE_2_ID",
        "env_label_key": "WHATSAPP_LINE_2_LABEL",
        "env_phone_key": "WHATSAPP_LINE_2_DISPLAY_PHONE",
        "internal_id": "bookings",
        "short_code": "BO",
        "default_label": "Bookings",
        "default_phone": "+20 100 000 1002",
        "default_service": "Bookings",
    },
    {
        "env_id_key": "WHATSAPP_LINE_3_ID",
        "env_label_key": "WHATSAPP_LINE_3_LABEL",
        "env_phone_key": "WHATSAPP_LINE_3_DISPLAY_PHONE",
        "internal_id": "emergency-desk",
        "short_code": "ED",
        "default_label": "Emergency Desk",
        "default_phone": "+20 100 000 1003",
        "default_service": "Emergency Desk",
    },
    {
        "env_id_key": "WHATSAPP_LINE_4_ID",
        "env_label_key": "WHATSAPP_LINE_4_LABEL",
        "env_phone_key": "WHATSAPP_LINE_4_DISPLAY_PHONE",
        "internal_id": "arabic-support",
        "short_code": "AS",
        "default_label": "Arabic Support",
        "default_phone": "+20 100 000 1004",
        "default_service": "Arabic Support",
    },
    {
        "env_id_key": "WHATSAPP_LINE_5_ID",
        "env_label_key": "WHATSAPP_LINE_5_LABEL",
        "env_phone_key": "WHATSAPP_LINE_5_DISPLAY_PHONE",
        "internal_id": "follow-up-care",
        "short_code": "FC",
        "default_label": "Follow-up Care",
        "default_phone": "+20 100 000 1005",
        "default_service": "Follow-up Care",
    },
]

def get_wa_lines_config():
    lines = []
    for d in WA_LINE_DEFAULTS:
        raw_id = os.environ.get(d["env_id_key"], "").strip()
        # Skip lines that haven't been configured with a real Meta phone number ID
        if not raw_id or raw_id.startswith("replace_with"):
            # Still include with a safe placeholder so existing DB rows get updated labels
            raw_id = f"UNCONFIGURED_{d['internal_id']}"
        label = os.environ.get(d["env_label_key"], d["default_label"])
        display_phone = os.environ.get(d["env_phone_key"], d["default_phone"])
        lines.append({
            "phone_number_id": raw_id,
            "internal_id": d["internal_id"],
            "short_code": d["short_code"],
            "label": label,
            "display_phone": display_phone,
            "default_service": d["default_service"],
        })
    return lines
