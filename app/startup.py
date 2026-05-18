"""Startup initialization: bootstrap admin user and WhatsApp lines."""
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.whatsapp import WhatsAppLine
from app.auth import get_password_hash
from app.config import BOOTSTRAP_ADMIN_USERNAME, BOOTSTRAP_ADMIN_PASSWORD, get_wa_lines_config
import logging

logger = logging.getLogger(__name__)


def run_startup():
    db = SessionLocal()
    try:
        _safe_migrate(db)
        _bootstrap_admin(db)
        _upsert_whatsapp_lines(db)
        _seed_demo_data(db)
    finally:
        db.close()


def _safe_migrate(db: Session):
    """Add new columns to existing tables without Alembic — idempotent."""
    from sqlalchemy import text
    new_cols = [
        ("doctors",             "photo_url",             "VARCHAR(500)"),
        ("doctors",             "languages",             "VARCHAR(300)"),
        ("doctors",             "consultation_fee_note", "VARCHAR(200)"),
        ("doctors",             "available_on_portal",   "BOOLEAN DEFAULT TRUE"),
        ("patient_portal_otps", "purpose",               "VARCHAR(20) DEFAULT 'login'"),
        ("patient_portal_otps", "pending_data",          "TEXT"),
    ]
    for table, col, col_type in new_cols:
        try:
            # PostgreSQL supports IF NOT EXISTS
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"))
            db.commit()
        except Exception:
            db.rollback()
            try:
                # SQLite fallback (no IF NOT EXISTS support)
                db.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                db.commit()
            except Exception:
                db.rollback()  # Column already exists — safe to ignore


def _bootstrap_admin(db: Session):
    existing = db.query(User).filter(User.username == BOOTSTRAP_ADMIN_USERNAME).first()
    if not existing:
        admin = User(
            username=BOOTSTRAP_ADMIN_USERNAME,
            full_name="System Administrator",
            hashed_password=get_password_hash(BOOTSTRAP_ADMIN_PASSWORD),
            role=UserRole.super_admin,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        logger.info(f"Bootstrap admin '{BOOTSTRAP_ADMIN_USERNAME}' created.")
    else:
        logger.info(f"Admin '{BOOTSTRAP_ADMIN_USERNAME}' already exists.")


def _upsert_whatsapp_lines(db: Session):
    lines_config = get_wa_lines_config()
    for cfg in lines_config:
        # Find the canonical row: prefer match by phone_number_id, fall back to internal_id
        existing = db.query(WhatsAppLine).filter(
            WhatsAppLine.phone_number_id == cfg["phone_number_id"]
        ).first()
        if not existing:
            existing = db.query(WhatsAppLine).filter(
                WhatsAppLine.internal_id == cfg["internal_id"]
            ).first()

        if existing:
            # Clear internal_id on any OTHER row that would collide before we set ours
            conflict = db.query(WhatsAppLine).filter(
                WhatsAppLine.internal_id == cfg["internal_id"],
                WhatsAppLine.id != existing.id,
            ).first()
            if conflict:
                logger.warning(
                    f"Clearing duplicate internal_id '{cfg['internal_id']}' "
                    f"from stale row {conflict.id} (phone_number_id={conflict.phone_number_id})"
                )
                conflict.internal_id = f"STALE_{conflict.phone_number_id}"
                db.flush()

            existing.phone_number_id = cfg["phone_number_id"]
            existing.internal_id = cfg["internal_id"]
            existing.label = cfg["label"]
            existing.display_phone_number = cfg["display_phone"]
            existing.short_code = cfg["short_code"]
            existing.default_service = cfg["default_service"]
        else:
            line = WhatsAppLine(
                phone_number_id=cfg["phone_number_id"],
                internal_id=cfg["internal_id"],
                label=cfg["label"],
                display_phone_number=cfg["display_phone"],
                short_code=cfg["short_code"],
                default_service=cfg["default_service"],
                is_active=True,
            )
            db.add(line)
    db.commit()
    logger.info("WhatsApp lines upserted.")


def _seed_demo_data(db: Session):
    """Only seeds if DB is empty — safe for production."""
    from app.models.patient import Patient
    from app.models.doctor import Doctor
    from app.models.clinic import Clinic
    from app.models.whatsapp import Conversation, Message, MessageDirection, MessageType, ConversationStatus

    if db.query(Patient).count() > 0:
        return  # Already has data

    logger.info("Seeding demo data...")

    # Demo clinic
    clinic = Clinic(
        name="TMASI Medical Centre",
        address="123 Healthcare Ave",
        city="Cairo",
        country="Egypt",
        phone="+20 2 1234 5678",
        email="info@tmasi.com",
        specialties="General Practice, Cardiology, Pediatrics",
    )
    db.add(clinic)
    db.flush()

    # Demo doctors
    d1 = Doctor(name="Dr. Ahmed Hassan", specialty="Cardiology", phone="+20 100 1001001", clinic_id=clinic.id)
    d2 = Doctor(name="Dr. Sarah Mostafa", specialty="General Practice", phone="+20 100 1001002", clinic_id=clinic.id)
    db.add_all([d1, d2])
    db.flush()

    # Demo patients
    p1 = Patient(name="Mohamed Ali", phone="+20 111 2345678", country="Egypt", city="Cairo", service_type="International Care", request_details="Seeking cardiology consultation")
    p2 = Patient(name="Fatima Ibrahim", phone="+20 122 3456789", country="Saudi Arabia", city="Riyadh", service_type="Bookings", request_details="Follow-up appointment needed")
    p3 = Patient(name="John Smith", phone="+44 7700 900123", country="UK", city="London", service_type="International Care", request_details="Medical tourism inquiry")
    db.add_all([p1, p2, p3])
    db.flush()

    # Get WhatsApp lines
    lines = db.query(WhatsAppLine).all()
    if lines:
        line1 = lines[0]
        line2 = lines[1] if len(lines) > 1 else lines[0]

        # Demo conversations
        c1 = Conversation(
            whatsapp_line_id=line1.id,
            customer_whatsapp_id="201112345678",
            customer_name="Mohamed Ali",
            customer_phone="+20 111 2345678",
            status=ConversationStatus.open,
            patient_id=p1.id,
            last_message_preview="When is my next appointment?",
        )
        c2 = Conversation(
            whatsapp_line_id=line1.id,
            customer_whatsapp_id="201223456789",
            customer_name="Fatima Ibrahim",
            customer_phone="+20 122 3456789",
            status=ConversationStatus.open,
            patient_id=p2.id,
            last_message_preview="I need to reschedule",
        )
        c3 = Conversation(
            whatsapp_line_id=line2.id,
            customer_whatsapp_id="447700900123",
            customer_name="John Smith",
            customer_phone="+44 7700 900123",
            status=ConversationStatus.open,
            patient_id=p3.id,
            last_message_preview="Hello, I'm interested in your services",
        )
        db.add_all([c1, c2, c3])
        db.flush()

        # Demo messages
        msgs = [
            Message(conversation_id=c1.id, direction=MessageDirection.inbound, message_type=MessageType.text, body="Hello, when is my next appointment with Dr. Hassan?", status="received"),
            Message(conversation_id=c1.id, direction=MessageDirection.outbound, message_type=MessageType.text, body="Hello Mohamed! Your appointment is scheduled for next Tuesday at 10 AM.", status="read"),
            Message(conversation_id=c1.id, direction=MessageDirection.inbound, message_type=MessageType.text, body="When is my next appointment?", status="received"),
            Message(conversation_id=c2.id, direction=MessageDirection.inbound, message_type=MessageType.text, body="Hello, I need to reschedule my appointment", status="received"),
            Message(conversation_id=c2.id, direction=MessageDirection.outbound, message_type=MessageType.text, body="Of course, Fatima. Which date works better for you?", status="delivered"),
            Message(conversation_id=c2.id, direction=MessageDirection.inbound, message_type=MessageType.text, body="I need to reschedule", status="received"),
            Message(conversation_id=c3.id, direction=MessageDirection.inbound, message_type=MessageType.text, body="Hello, I'm interested in your services", status="received"),
        ]
        db.add_all(msgs)

    db.commit()
    logger.info("Demo data seeded successfully.")
