from sqlalchemy import Column, String, Boolean, DateTime, Text
from datetime import datetime, timezone
import uuid
from app.database import Base


class PatientPortalOTP(Base):
    __tablename__ = "patient_portal_otps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    identifier = Column(String(200), nullable=False, index=True)  # email used to log in / register
    patient_id = Column(String(36), nullable=True, index=True)    # resolved after lookup (login) or after creation (register)
    code = Column(String(10), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    # "login" = existing patient, "register" = new account creation
    purpose = Column(String(20), nullable=False, default="login")
    # JSON blob of registration form data (name, phone, country, city, service_type)
    pending_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
