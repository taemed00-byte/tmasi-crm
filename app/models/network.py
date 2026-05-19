"""Network Management — extended provider (clinic) contracts, tariffs, performance."""
from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, ForeignKey,
    Enum as SAEnum, Integer, Float, JSON,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum
from app.database import Base


class ProviderCategory(str, enum.Enum):
    preferred   = "preferred"
    standard    = "standard"
    restricted  = "restricted"
    blacklisted = "blacklisted"


class ProviderType(str, enum.Enum):
    hospital   = "hospital"
    clinic     = "clinic"
    pharmacy   = "pharmacy"
    laboratory = "laboratory"
    ambulance  = "ambulance"
    specialist = "specialist"
    other      = "other"


class ContractStatus(str, enum.Enum):
    draft      = "draft"
    active     = "active"
    expired    = "expired"
    terminated = "terminated"


class ProviderContract(Base):
    __tablename__ = "provider_contracts"

    id              = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id     = Column(String(36), ForeignKey("clinics.id"), nullable=False, index=True)
    contract_number = Column(String(50), nullable=False, unique=True)
    status          = Column(SAEnum(ContractStatus), default=ContractStatus.draft, nullable=False)

    start_date   = Column(DateTime, nullable=True)
    end_date     = Column(DateTime, nullable=True)
    auto_renewal = Column(Boolean, default=False)

    credit_terms_days    = Column(Integer, nullable=True, default=30)
    discount_percentage  = Column(Float, nullable=True, default=0.0)
    payment_currency     = Column(String(10), nullable=True, default="USD")

    scope_notes    = Column(Text, nullable=True)
    exclusions     = Column(Text, nullable=True)
    document_url   = Column(String(500), nullable=True)

    created_by  = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(DateTime,
                         default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

    provider = relationship("Clinic", foreign_keys=[provider_id])
    creator  = relationship("User",   foreign_keys=[created_by])
    tariffs  = relationship("ProviderTariff", back_populates="contract",
                            cascade="all, delete-orphan")


class ProviderTariff(Base):
    __tablename__ = "provider_tariffs"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id = Column(String(36), ForeignKey("provider_contracts.id"), nullable=False, index=True)

    service_category = Column(String(200), nullable=False)
    service_name     = Column(String(300), nullable=False)
    pricing_model    = Column(String(100), nullable=True)   # fixed / per-night / per-km / DRG
    unit_cost        = Column(Float, nullable=False, default=0.0)
    currency         = Column(String(10), nullable=True, default="USD")
    notes            = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    contract = relationship("ProviderContract", back_populates="tariffs")
