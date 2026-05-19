from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Enum as SAEnum, Integer
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum
from app.database import Base


class PatientStatus(str, enum.Enum):
    new = "new"
    active = "active"
    follow_up = "follow_up"
    discharged = "discharged"
    inactive = "inactive"


class PatientPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class Patient(Base):
    __tablename__ = "patients"

    id                      = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name                    = Column(String(200), nullable=False)
    phone                   = Column(String(50), nullable=False, index=True)
    email                   = Column(String(200), nullable=True, index=True)
    country                 = Column(String(100), nullable=True)
    city                    = Column(String(100), nullable=True)
    location                = Column(String(300), nullable=True)
    service_type            = Column(String(200), nullable=True)
    request_details         = Column(Text, nullable=True)
    priority                = Column(SAEnum(PatientPriority), default=PatientPriority.normal)
    status                  = Column(SAEnum(PatientStatus), default=PatientStatus.new)

    # Extended demographics
    date_of_birth           = Column(String(20), nullable=True)   # ISO date string YYYY-MM-DD
    nationality             = Column(String(100), nullable=True)
    passport_number         = Column(String(100), nullable=True)
    medical_record_number   = Column(String(100), nullable=True, index=True)
    language_preference     = Column(String(100), nullable=True)

    # Insurance
    insurance_provider      = Column(String(200), nullable=True)
    insurance_policy_number = Column(String(100), nullable=True)

    # Internal notes (staff only)
    notes_internal          = Column(Text, nullable=True)

    created_by              = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at              = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at              = Column(DateTime,
                                     default=lambda: datetime.now(timezone.utc),
                                     onupdate=lambda: datetime.now(timezone.utc))

    conversations = relationship("Conversation", back_populates="patient", foreign_keys="[Conversation.patient_id]")
    documents = relationship("PatientDocument", back_populates="patient")
    media_files = relationship("MediaFile", back_populates="patient", foreign_keys="[MediaFile.patient_id]")
    appointments = relationship("Appointment", back_populates="patient")


class PatientDocument(Base):
    __tablename__ = "patient_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    file_name = Column(String(500), nullable=False)
    original_name = Column(String(500), nullable=True)
    mime_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    storage_path = Column(String(1000), nullable=True)
    description = Column(Text, nullable=True)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    patient = relationship("Patient", back_populates="documents")

