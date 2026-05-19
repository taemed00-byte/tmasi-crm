from sqlalchemy import Column, String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum
from app.database import Base


class UserRole(str, enum.Enum):
    super_admin  = "super_admin"
    clinic_admin = "clinic_admin"
    case_manager = "case_manager"
    agent        = "agent"
    finance      = "finance"
    doctor       = "doctor"


class UserDepartment(str, enum.Enum):
    operations      = "operations"
    network         = "network"
    finance         = "finance"
    sales           = "sales"
    case_management = "case_management"
    medical         = "medical"
    management      = "management"


class User(Base):
    __tablename__ = "users"

    id              = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username        = Column(String(100), unique=True, nullable=False, index=True)
    email           = Column(String(200), unique=True, nullable=True)
    full_name       = Column(String(200), nullable=True)
    hashed_password = Column(String(256), nullable=False)
    role            = Column(SAEnum(UserRole), default=UserRole.agent, nullable=False)
    department      = Column(String(100), nullable=True)
    phone_extension = Column(String(50), nullable=True)
    is_active       = Column(Boolean, default=True)
    last_active_at  = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime,
                             default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))
