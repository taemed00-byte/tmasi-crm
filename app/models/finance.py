"""Finance module — invoices and payments."""
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Enum as SAEnum, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum
from app.database import Base


class InvoiceStatus(str, enum.Enum):
    draft    = "draft"
    sent     = "sent"
    partial  = "partial"
    paid     = "paid"
    overdue  = "overdue"
    void     = "void"


class PaymentMethod(str, enum.Enum):
    cash        = "cash"
    card        = "card"
    bank_transfer = "bank_transfer"
    insurance   = "insurance"
    crypto      = "crypto"
    other       = "other"


class Invoice(Base):
    __tablename__ = "invoices"

    id               = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_number   = Column(String(30), unique=True, nullable=False, index=True)
    case_id          = Column(String(36), ForeignKey("cases.id"), nullable=True, index=True)
    patient_id       = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)

    # Billing target
    issued_to_name   = Column(String(200), nullable=True)   # person or company billed
    issued_to_email  = Column(String(200), nullable=True)

    # Amounts (all stored in base currency)
    subtotal         = Column(Float, nullable=False, default=0.0)
    tax_amount       = Column(Float, nullable=False, default=0.0)
    discount_amount  = Column(Float, nullable=False, default=0.0)
    total_amount     = Column(Float, nullable=False, default=0.0)
    paid_amount      = Column(Float, nullable=False, default=0.0)
    currency         = Column(String(10), nullable=False, default="USD")

    status           = Column(SAEnum(InvoiceStatus), default=InvoiceStatus.draft, nullable=False, index=True)
    due_date         = Column(DateTime, nullable=True)
    paid_at          = Column(DateTime, nullable=True)

    notes            = Column(Text, nullable=True)
    created_by       = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at       = Column(DateTime,
                              default=lambda: datetime.now(timezone.utc),
                              onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    case             = relationship("Case", foreign_keys=[case_id])
    patient          = relationship("Patient", foreign_keys=[patient_id])
    creator          = relationship("User", foreign_keys=[created_by])
    items            = relationship("InvoiceItem", back_populates="invoice",
                                    order_by="InvoiceItem.created_at",
                                    cascade="all, delete-orphan")
    payments         = relationship("Payment", back_populates="invoice",
                                    order_by="Payment.received_at",
                                    cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id  = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    description = Column(String(500), nullable=False)
    quantity    = Column(Float, nullable=False, default=1.0)
    unit_price  = Column(Float, nullable=False, default=0.0)
    total       = Column(Float, nullable=False, default=0.0)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    invoice     = relationship("Invoice", back_populates="items")


class Payment(Base):
    __tablename__ = "payments"

    id               = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id       = Column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    amount           = Column(Float, nullable=False)
    currency         = Column(String(10), nullable=False, default="USD")
    method           = Column(SAEnum(PaymentMethod), default=PaymentMethod.cash)
    reference_number = Column(String(200), nullable=True)  # bank ref, receipt no, etc.
    notes            = Column(Text, nullable=True)
    received_by      = Column(String(36), ForeignKey("users.id"), nullable=True)
    received_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    invoice          = relationship("Invoice", back_populates="payments")
    receiver         = relationship("User", foreign_keys=[received_by])
