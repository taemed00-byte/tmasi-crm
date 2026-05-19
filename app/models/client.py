"""Client Management — insurance companies, contracts, sales pipeline."""
from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, ForeignKey,
    Enum as SAEnum, Integer, Float,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum
from app.database import Base


class ClientType(str, enum.Enum):
    insurance_company  = "insurance_company"
    assistance_company = "assistance_company"
    corporate          = "corporate"
    other              = "other"


class ClientStatus(str, enum.Enum):
    prospect = "prospect"
    active   = "active"
    inactive = "inactive"
    churned  = "churned"


class ClientContractStatus(str, enum.Enum):
    draft          = "draft"
    under_review   = "under_review"
    active         = "active"
    expired        = "expired"
    terminated     = "terminated"


class PipelineStage(str, enum.Enum):
    lead        = "lead"
    qualified   = "qualified"
    proposal    = "proposal"
    negotiation = "negotiation"
    contract_sent = "contract_sent"
    won         = "won"
    lost        = "lost"


class BillingFrequency(str, enum.Enum):
    per_case   = "per_case"
    monthly    = "monthly"
    quarterly  = "quarterly"


class Client(Base):
    __tablename__ = "clients"

    id           = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name         = Column(String(300), nullable=False, index=True)
    client_type  = Column(SAEnum(ClientType), default=ClientType.insurance_company, nullable=False)
    status       = Column(SAEnum(ClientStatus), default=ClientStatus.prospect, nullable=False, index=True)

    country              = Column(String(100), nullable=True)
    operating_countries  = Column(Text, nullable=True)   # comma-separated

    # Contacts
    primary_contact_name  = Column(String(200), nullable=True)
    primary_contact_phone = Column(String(50), nullable=True)
    primary_contact_email = Column(String(200), nullable=True)
    claims_contact_name   = Column(String(200), nullable=True)
    claims_contact_phone  = Column(String(50), nullable=True)
    claims_contact_email  = Column(String(200), nullable=True)
    finance_contact_name  = Column(String(200), nullable=True)
    finance_contact_email = Column(String(200), nullable=True)

    account_manager_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    annual_case_volume_target = Column(Integer, nullable=True)
    annual_revenue_target_usd = Column(Float, nullable=True)
    client_since              = Column(DateTime, nullable=True)

    notes      = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    account_manager = relationship("User", foreign_keys=[account_manager_id])
    contracts       = relationship("ClientContract", back_populates="client",
                                   cascade="all, delete-orphan")
    pipeline_items  = relationship("SalesPipeline", back_populates="client",
                                   cascade="all, delete-orphan")


class ClientContract(Base):
    __tablename__ = "client_contracts"

    id              = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id       = Column(String(36), ForeignKey("clients.id"), nullable=False, index=True)
    contract_number = Column(String(50), nullable=False, unique=True)
    status          = Column(SAEnum(ClientContractStatus), default=ClientContractStatus.draft, nullable=False)

    start_date   = Column(DateTime, nullable=True)
    end_date     = Column(DateTime, nullable=True)
    auto_renewal = Column(Boolean, default=False)

    billing_frequency    = Column(SAEnum(BillingFrequency), default=BillingFrequency.per_case)
    payment_terms_days   = Column(Integer, nullable=True, default=30)
    billing_currency     = Column(String(10), nullable=True, default="USD")

    # Fee structure
    management_fee_type      = Column(String(50), nullable=True)   # per_case / retainer / percentage
    management_fee_value     = Column(Float, nullable=True)
    max_reimbursement_notes  = Column(Text, nullable=True)

    service_scope      = Column(Text, nullable=True)
    sla_commitments    = Column(Text, nullable=True)
    exclusions         = Column(Text, nullable=True)
    reporting_schedule = Column(String(200), nullable=True)
    document_url       = Column(String(500), nullable=True)

    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    client  = relationship("Client", back_populates="contracts")
    creator = relationship("User",   foreign_keys=[created_by])


class SalesPipeline(Base):
    __tablename__ = "sales_pipeline"

    id        = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False, index=True)

    stage        = Column(SAEnum(PipelineStage), default=PipelineStage.lead, nullable=False, index=True)
    title        = Column(String(300), nullable=False)
    description  = Column(Text, nullable=True)
    value_usd    = Column(Float, nullable=True)
    probability  = Column(Integer, nullable=True)   # 0-100 %

    expected_close = Column(DateTime, nullable=True)
    closed_at      = Column(DateTime, nullable=True)
    lost_reason    = Column(Text, nullable=True)

    owner_id   = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    client = relationship("Client", back_populates="pipeline_items")
    owner  = relationship("User",   foreign_keys=[owner_id])
