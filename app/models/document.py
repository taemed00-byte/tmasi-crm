"""Case Document Management."""
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Integer, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum
from app.database import Base


class DocumentType(str, enum.Enum):
    medical_report         = "medical_report"
    gop                    = "gop"
    passport               = "passport"
    insurance_card         = "insurance_card"
    lab_results            = "lab_results"
    discharge_summary      = "discharge_summary"
    claim_form             = "claim_form"
    pre_auth_letter        = "pre_auth_letter"
    provider_bill          = "provider_bill"
    evacuation_document    = "evacuation_document"
    contract               = "contract"
    other                  = "other"


class CaseDocument(Base):
    __tablename__ = "case_documents"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id     = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    doc_type    = Column(SAEnum(DocumentType), default=DocumentType.other, nullable=False)
    filename    = Column(String(300), nullable=False)
    file_path   = Column(String(500), nullable=False)
    file_size   = Column(Integer, nullable=True)
    mime_type   = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    is_latest   = Column(Boolean, default=True)
    version     = Column(Integer, default=1)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    case     = relationship("Case",  foreign_keys=[case_id])
    uploader = relationship("User",  foreign_keys=[uploaded_by])
