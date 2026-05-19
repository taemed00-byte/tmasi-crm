"""Audit Trail — immutable log of every system action."""
from sqlalchemy import Column, String, DateTime, Text, Enum as SAEnum
from datetime import datetime, timezone
import uuid
import enum
from app.database import Base


class AuditAction(str, enum.Enum):
    create  = "create"
    update  = "update"
    delete  = "delete"
    view    = "view"
    export  = "export"
    login   = "login"
    logout  = "logout"
    approve = "approve"
    upload  = "upload"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp   = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    user_id     = Column(String(36), nullable=True, index=True)
    username    = Column(String(100), nullable=True)
    user_role   = Column(String(50), nullable=True)
    ip_address  = Column(String(60), nullable=True)

    action      = Column(SAEnum(AuditAction), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id   = Column(String(36), nullable=True, index=True)
    summary     = Column(Text, nullable=True)

    before_state = Column(Text, nullable=True)   # JSON string
    after_state  = Column(Text, nullable=True)   # JSON string
    session_id   = Column(String(100), nullable=True)
    user_agent   = Column(String(300), nullable=True)
