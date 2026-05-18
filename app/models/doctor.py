from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    specialty = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(200), nullable=True)
    clinic_id = Column(String(36), ForeignKey("clinics.id"), nullable=True)
    bio = Column(Text, nullable=True)
    photo_url = Column(String(500), nullable=True)              # URL to profile photo
    languages = Column(String(300), nullable=True)              # comma-separated, e.g. "English, Arabic, French"
    consultation_fee_note = Column(String(200), nullable=True)  # e.g. "From $150 USD"
    available_on_portal = Column(Boolean, default=True)         # visible in patient portal
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    clinic = relationship("Clinic", back_populates="doctors")
    appointments = relationship("Appointment", back_populates="doctor")
