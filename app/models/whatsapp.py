from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum
from app.database import Base


class MessageDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"
    note = "note"


class MessageType(str, enum.Enum):
    text = "text"
    image = "image"
    document = "document"
    audio = "audio"
    video = "video"
    location = "location"
    contact = "contact"
    sticker = "sticker"
    note = "note"


class MessageStatus(str, enum.Enum):
    sent = "sent"
    delivered = "delivered"
    read = "read"
    failed = "failed"
    received = "received"


class ConversationStatus(str, enum.Enum):
    open = "open"
    pending = "pending"
    resolved = "resolved"
    spam = "spam"


class ConversationPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class WhatsAppLine(Base):
    __tablename__ = "whatsapp_lines"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone_number_id = Column(String(100), unique=True, nullable=False, index=True)
    internal_id = Column(String(100), unique=True, nullable=True)
    label = Column(String(200), nullable=False)
    display_phone_number = Column(String(50), nullable=True)
    short_code = Column(String(10), nullable=True)
    default_service = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    conversations = relationship("Conversation", back_populates="whatsapp_line")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    whatsapp_line_id = Column(String(36), ForeignKey("whatsapp_lines.id"), nullable=False, index=True)
    customer_whatsapp_id = Column(String(50), nullable=False, index=True)
    customer_name = Column(String(200), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    status = Column(SAEnum(ConversationStatus), default=ConversationStatus.open, nullable=False)
    priority = Column(SAEnum(ConversationPriority), default=ConversationPriority.normal, nullable=False)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=True, index=True)
    assigned_agent_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    last_message_at = Column(DateTime, nullable=True)
    last_message_preview = Column(String(500), nullable=True)
    unread_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    whatsapp_line = relationship("WhatsAppLine", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")
    patient = relationship("Patient", back_populates="conversations", foreign_keys=[patient_id])
    media_files = relationship("MediaFile", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, index=True)
    whatsapp_message_id = Column(String(200), unique=True, nullable=True, index=True)
    direction = Column(SAEnum(MessageDirection), nullable=False)
    message_type = Column(SAEnum(MessageType), default=MessageType.text)
    body = Column(Text, nullable=True)
    status = Column(SAEnum(MessageStatus), default=MessageStatus.received)
    sender_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    media_file_id = Column(String(36), ForeignKey("media_files.id"), nullable=True)
    raw_payload = Column(Text, nullable=True)  # JSON string of raw WhatsApp payload
    timestamp = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="messages")
    media_file = relationship("MediaFile", foreign_keys=[media_file_id])


class MediaFile(Base):
    __tablename__ = "media_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    whatsapp_media_id = Column(String(200), nullable=True, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=True)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=True)
    file_name = Column(String(500), nullable=True)
    original_name = Column(String(500), nullable=True)
    mime_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    storage_path = Column(String(1000), nullable=True)
    storage_url = Column(String(1000), nullable=True)
    media_type = Column(String(50), nullable=True)  # image, document, audio, video
    caption = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="media_files", foreign_keys=[conversation_id])
    patient = relationship("Patient", back_populates="media_files", foreign_keys=[patient_id])
