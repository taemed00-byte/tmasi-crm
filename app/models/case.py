"""Case Management Engine -- core domain model."""
from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, ForeignKey,
    Enum as SAEnum, Integer, Float,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum
from app.database import Base


class CaseStatus(str, enum.Enum):
    intake           = "intake"
    triage           = "triage"
    active           = "active"
    pending_provider = "pending_provider"
    pending_patient  = "pending_patient"
    treatment        = "treatment"
    follow_up        = "follow_up"
    closed           = "closed"
    cancelled        = "cancelled"


class CasePriority(str, enum.Enum):
    low      = "low"
    normal   = "normal"
    high     = "high"
    urgent   = "urgent"
    critical = "critical"


class CaseType(str, enum.Enum):
    medical_tourism    = "medical_tourism"
    international_care = "international_care"
    local_booking      = "local_booking"
    emergency          = "emergency"
    follow_up          = "follow_up"
    second_opinion     = "second_opinion"
    insurance_claim    = "insurance_claim"
    teleconsultation   = "teleconsultation"


class NoteType(str, enum.Enum):
    general    = "general"
    medical    = "medical"
    financial  = "financial"
    escalation = "escalation"
    system     = "system"


class TaskStatus(str, enum.Enum):
    pending     = "pending"
    in_progress = "in_progress"
    done        = "done"
    skipped     = "skipped"


# Convenience groupings used by the API filter
OPEN_STATUSES = [
    CaseStatus.intake, CaseStatus.triage, CaseStatus.active,
    CaseStatus.pending_provider, CaseStatus.pending_patient,
    CaseStatus.treatment, CaseStatus.follow_up,
]
CLOSED_STATUSES = [CaseStatus.closed, CaseStatus.cancelled]


class Case(Base):
    __tablename__ = "cases"

    id               = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_number      = Column(String(30), unique=True, nullable=False, index=True)
    patient_id       = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    assigned_to      = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    doctor_id        = Column(String(36), ForeignKey("doctors.id"), nullable=True)
    clinic_id        = Column(String(36), ForeignKey("clinics.id"), nullable=True)

    type             = Column(SAEnum(CaseType), default=CaseType.international_care, nullable=False)
    status           = Column(SAEnum(CaseStatus), default=CaseStatus.intake, nullable=False, index=True)
    priority         = Column(SAEnum(CasePriority), default=CasePriority.normal, nullable=False)

    title            = Column(String(300), nullable=False)
    description      = Column(Text, nullable=True)
    service_type     = Column(String(200), nullable=True)

    country_of_origin    = Column(String(100), nullable=True)
    treatment_country    = Column(String(100), nullable=True)

    estimated_cost   = Column(Float, nullable=True)
    currency         = Column(String(10), nullable=True, default="USD")

    insurance_provider      = Column(String(200), nullable=True)
    insurance_policy_number = Column(String(100), nullable=True)
    insurance_pre_auth      = Column(Boolean, default=False)

    sla_hours        = Column(Integer, nullable=True, default=24)
    sla_due_at       = Column(DateTime, nullable=True)
    sla_breached     = Column(Boolean, default=False)

    opened_at        = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at        = Column(DateTime, nullable=True)

    created_by       = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at       = Column(DateTime,
                              default=lambda: datetime.now(timezone.utc),
                              onupdate=lambda: datetime.now(timezone.utc))

    patient     = relationship("Patient", foreign_keys=[patient_id])
    assignee    = relationship("User", foreign_keys=[assigned_to])
    creator     = relationship("User", foreign_keys=[created_by])
    doctor      = relationship("Doctor", foreign_keys=[doctor_id])
    clinic      = relationship("Clinic", foreign_keys=[clinic_id])
    notes       = relationship("CaseNote", back_populates="case",
                               order_by="CaseNote.created_at", cascade="all, delete-orphan")
    tasks       = relationship("CaseTask", back_populates="case",
                               order_by="CaseTask.created_at", cascade="all, delete-orphan")
    escalations = relationship("CaseEscalation", back_populates="case",
                               order_by="CaseEscalation.created_at", cascade="all, delete-orphan")


class CaseNote(Base):
    __tablename__ = "case_notes"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id     = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    author_id   = Column(String(36), ForeignKey("users.id"), nullable=True)
    body        = Column(Text, nullable=False)
    note_type   = Column(SAEnum(NoteType), default=NoteType.general)
    is_internal = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    case   = relationship("Case", back_populates="notes")
    author = relationship("User", foreign_keys=[author_id])


class CaseTask(Base):
    __tablename__ = "case_tasks"

    id           = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id      = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    assigned_to  = Column(String(36), ForeignKey("users.id"), nullable=True)
    title        = Column(String(300), nullable=False)
    description  = Column(Text, nullable=True)
    due_at       = Column(DateTime, nullable=True)
    status       = Column(SAEnum(TaskStatus), default=TaskStatus.pending)
    completed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_by   = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    case      = relationship("Case", back_populates="tasks")
    assignee  = relationship("User", foreign_keys=[assigned_to])
    completer = relationship("User", foreign_keys=[completed_by])
    creator   = relationship("User", foreign_keys=[created_by])


class CaseEscalation(Base):
    __tablename__ = "case_escalations"

    id           = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id      = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    escalated_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    escalated_to = Column(String(36), ForeignKey("users.id"), nullable=True)
    reason       = Column(Text, nullable=False)
    resolved_at  = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    case    = relationship("Case", back_populates="escalations")
    by_user = relationship("User", foreign_keys=[escalated_by])
    to_user = relationship("User", foreign_keys=[escalated_to])
