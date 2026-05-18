import json
import os
import uuid
import httpx
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.models.whatsapp import (
    WhatsAppLine, Conversation, Message, MediaFile,
    MessageDirection, MessageType, MessageStatus, ConversationStatus, ConversationPriority
)
from app.models.patient import Patient
from app.config import (
    WHATSAPP_ACCESS_TOKEN, WHATSAPP_VERIFY_TOKEN, WHATSAPP_GRAPH_URL, UPLOAD_DIR
)
from pydantic import BaseModel

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])
logger = logging.getLogger(__name__)


# ─── Webhook ───────────────────────────────────────────────────────────────

@router.get("/webhook")
def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(content=challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored"}

    try:
        _process_webhook(body, db)
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
    return {"status": "ok"}


def _process_webhook(body: dict, db: Session):
    entries = body.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id", "")

            # Route to correct WhatsApp line
            wa_line = _resolve_whatsapp_line(phone_number_id, db)

            # Process messages
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])
            contact_map = {c["wa_id"]: c.get("profile", {}).get("name", "") for c in contacts}

            for msg in messages:
                _handle_inbound_message(msg, wa_line, contact_map, db)

            # Process status updates
            statuses = value.get("statuses", [])
            for st in statuses:
                _handle_status_update(st, db)


def _resolve_whatsapp_line(phone_number_id: str, db: Session) -> WhatsAppLine:
    line = db.query(WhatsAppLine).filter(
        WhatsAppLine.phone_number_id == phone_number_id
    ).first()
    if not line:
        # Fallback: create unknown line
        line = WhatsAppLine(
            phone_number_id=phone_number_id,
            internal_id=phone_number_id,
            label="Unknown WhatsApp Line",
            display_phone_number=phone_number_id,
            short_code="UN",
            default_service="Unknown",
            is_active=True,
        )
        db.add(line)
        db.commit()
        db.refresh(line)
    return line


def _handle_inbound_message(msg: dict, wa_line: WhatsAppLine, contact_map: dict, db: Session):
    wa_msg_id = msg.get("id", "")
    from_id = msg.get("from", "")
    msg_type = msg.get("type", "text")
    ts = msg.get("timestamp", "")

    # Idempotency check
    if wa_msg_id and db.query(Message).filter(Message.whatsapp_message_id == wa_msg_id).first():
        return

    # Get or create conversation
    conv = db.query(Conversation).filter(
        Conversation.whatsapp_line_id == wa_line.id,
        Conversation.customer_whatsapp_id == from_id,
    ).first()
    customer_name = contact_map.get(from_id, "")

    if not conv:
        conv = Conversation(
            whatsapp_line_id=wa_line.id,
            customer_whatsapp_id=from_id,
            customer_name=customer_name or from_id,
            customer_phone=f"+{from_id}",
            status=ConversationStatus.open,
        )
        db.add(conv)
        db.flush()
    elif customer_name and not conv.customer_name:
        conv.customer_name = customer_name

    # Extract body and media
    body_text = ""
    media_file_id = None
    msg_type_enum = MessageType.text

    if msg_type == "text":
        body_text = msg.get("text", {}).get("body", "")
        msg_type_enum = MessageType.text
    elif msg_type == "image":
        img = msg.get("image", {})
        body_text = img.get("caption", "")
        msg_type_enum = MessageType.image
        media_file_id = _save_media_ref(img.get("id"), "image", img.get("mime_type", "image/jpeg"), conv.id, db)
    elif msg_type == "document":
        doc = msg.get("document", {})
        body_text = doc.get("caption", doc.get("filename", "Document"))
        msg_type_enum = MessageType.document
        media_file_id = _save_media_ref(doc.get("id"), "document", doc.get("mime_type", "application/octet-stream"), conv.id, db, file_name=doc.get("filename"))
    elif msg_type == "audio":
        body_text = "[Audio message]"
        msg_type_enum = MessageType.audio
        audio = msg.get("audio", {})
        media_file_id = _save_media_ref(audio.get("id"), "audio", audio.get("mime_type", "audio/ogg"), conv.id, db)
    elif msg_type == "video":
        body_text = "[Video message]"
        msg_type_enum = MessageType.video
        video = msg.get("video", {})
        media_file_id = _save_media_ref(video.get("id"), "video", video.get("mime_type", "video/mp4"), conv.id, db)
    elif msg_type == "location":
        loc = msg.get("location", {})
        body_text = f"📍 Location: {loc.get('name', '')} ({loc.get('latitude')}, {loc.get('longitude')})"
        msg_type_enum = MessageType.location
    elif msg_type == "contacts":
        contacts_list = msg.get("contacts", [])
        names = [c.get("name", {}).get("formatted_name", "") for c in contacts_list]
        body_text = f"Contact: {', '.join(names)}"
        msg_type_enum = MessageType.contact

    timestamp_dt = datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else datetime.now(timezone.utc)

    message = Message(
        conversation_id=conv.id,
        whatsapp_message_id=wa_msg_id,
        direction=MessageDirection.inbound,
        message_type=msg_type_enum,
        body=body_text,
        status=MessageStatus.received,
        media_file_id=media_file_id,
        raw_payload=json.dumps(msg),
        timestamp=timestamp_dt,
    )
    db.add(message)

    conv.last_message_at = timestamp_dt
    conv.last_message_preview = body_text[:200] if body_text else f"[{msg_type}]"
    conv.unread_count = (conv.unread_count or 0) + 1
    db.commit()


def _save_media_ref(media_id: str, media_type: str, mime_type: str, conv_id: str, db: Session, file_name: str = None) -> Optional[str]:
    if not media_id:
        return None
    mf = MediaFile(
        whatsapp_media_id=media_id,
        conversation_id=conv_id,
        mime_type=mime_type,
        media_type=media_type,
        file_name=file_name or media_id,
    )
    db.add(mf)
    db.flush()
    return mf.id


def _handle_status_update(st: dict, db: Session):
    wa_msg_id = st.get("id")
    new_status = st.get("status")
    if not wa_msg_id or not new_status:
        return
    msg = db.query(Message).filter(Message.whatsapp_message_id == wa_msg_id).first()
    if msg:
        try:
            msg.status = MessageStatus(new_status)
            db.commit()
        except Exception:
            pass


# ─── WhatsApp Lines ─────────────────────────────────────────────────────────

@router.get("/lines")
def get_lines(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    lines = db.query(WhatsAppLine).filter(WhatsAppLine.is_active == True).all()
    result = []
    for line in lines:
        open_count = db.query(Conversation).filter(
            Conversation.whatsapp_line_id == line.id,
            Conversation.status == ConversationStatus.open
        ).count()
        result.append({
            "id": line.id,
            "phone_number_id": line.phone_number_id,
            "internal_id": line.internal_id,
            "label": line.label,
            "display_phone_number": line.display_phone_number,
            "short_code": line.short_code,
            "default_service": line.default_service,
            "open_count": open_count,
        })
    return result


# ─── Conversations ───────────────────────────────────────────────────────────

@router.get("/conversations")
def get_conversations(
    line_id: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(Conversation)
    if line_id:
        q = q.filter(Conversation.whatsapp_line_id == line_id)
    if status:
        q = q.filter(Conversation.status == status)
    if search:
        q = q.filter(
            Conversation.customer_name.ilike(f"%{search}%") |
            Conversation.customer_phone.ilike(f"%{search}%") |
            Conversation.customer_whatsapp_id.ilike(f"%{search}%")
        )
    q = q.order_by(Conversation.last_message_at.desc().nullslast())
    total = q.count()
    convs = q.offset(offset).limit(limit).all()

    result = []
    for c in convs:
        patient_name = None
        if c.patient:
            patient_name = c.patient.name
        line = db.query(WhatsAppLine).filter(WhatsAppLine.id == c.whatsapp_line_id).first()
        result.append({
            "id": c.id,
            "whatsapp_line_id": c.whatsapp_line_id,
            "line_label": line.label if line else "",
            "line_short_code": line.short_code if line else "",
            "customer_whatsapp_id": c.customer_whatsapp_id,
            "customer_name": c.customer_name,
            "customer_phone": c.customer_phone,
            "status": c.status,
            "priority": c.priority,
            "patient_id": c.patient_id,
            "patient_name": patient_name,
            "has_patient_file": c.patient_id is not None,
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
            "last_message_preview": c.last_message_preview,
            "unread_count": c.unread_count,
            "created_at": c.created_at.isoformat(),
        })
    return {"total": total, "items": result}


@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not c:
        raise HTTPException(404, "Conversation not found")

    # Reset unread count
    c.unread_count = 0
    db.commit()

    line = db.query(WhatsAppLine).filter(WhatsAppLine.id == c.whatsapp_line_id).first()
    messages = []
    for m in c.messages:
        media_url = None
        if m.media_file:
            local_exists = bool(
                m.media_file.storage_path and
                os.path.exists(m.media_file.storage_path)
            )
            if local_exists:
                # Serve from local disk
                media_url = f"/api/media/files/{m.media_file.id}"
            elif m.media_file.whatsapp_media_id:
                # Fall back to live WhatsApp CDN proxy
                media_url = f"/api/whatsapp/media/{m.media_file.whatsapp_media_id}"
            elif m.media_file.storage_path:
                # Path recorded but file lost (e.g. Render redeploy wipe)
                media_url = f"/api/media/files/{m.media_file.id}"  # will 404 gracefully
        messages.append({
            "id": m.id,
            "direction": m.direction,
            "message_type": m.message_type,
            "body": m.body,
            "status": m.status,
            "media_file_id": m.media_file_id,
            "media_url": media_url,
            "media_mime_type": m.media_file.mime_type if m.media_file else None,
            "media_name": m.media_file.original_name or m.media_file.file_name if m.media_file else None,
            "timestamp": m.timestamp.isoformat() if m.timestamp else m.created_at.isoformat(),
            "created_at": m.created_at.isoformat(),
        })

    patient_data = None
    if c.patient:
        p = c.patient
        patient_data = {
            "id": p.id, "name": p.name, "phone": p.phone, "email": p.email,
            "country": p.country, "city": p.city, "location": p.location,
            "service_type": p.service_type, "request_details": p.request_details,
            "priority": p.priority, "status": p.status,
        }

    return {
        "id": c.id,
        "whatsapp_line_id": c.whatsapp_line_id,
        "line_label": line.label if line else "",
        "line_short_code": line.short_code if line else "",
        "line_phone_number_id": line.phone_number_id if line else "",
        "customer_whatsapp_id": c.customer_whatsapp_id,
        "customer_name": c.customer_name,
        "customer_phone": c.customer_phone,
        "status": c.status,
        "priority": c.priority,
        "patient_id": c.patient_id,
        "patient": patient_data,
        "messages": messages,
        "created_at": c.created_at.isoformat(),
    }


class UpdateConversationRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    customer_name: Optional[str] = None


@router.patch("/conversations/{conv_id}")
def update_conversation(conv_id: str, req: UpdateConversationRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not c:
        raise HTTPException(404, "Not found")
    if req.status:
        c.status = req.status
    if req.priority:
        c.priority = req.priority
    if req.customer_name:
        c.customer_name = req.customer_name
    db.commit()
    return {"ok": True}


# ─── Send Message ─────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    conversation_id: str
    message: str
    is_note: bool = False


@router.post("/send")
async def send_message(req: SendMessageRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = db.query(Conversation).filter(Conversation.id == req.conversation_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    line = db.query(WhatsAppLine).filter(WhatsAppLine.id == conv.whatsapp_line_id).first()
    wa_msg_id = None

    if not req.is_note and WHATSAPP_ACCESS_TOKEN and line and line.phone_number_id and line.phone_number_id.isdigit():
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{WHATSAPP_GRAPH_URL}/{line.phone_number_id}/messages",
                    headers={
                        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "to": conv.customer_whatsapp_id,
                        "type": "text",
                        "text": {"body": req.message},
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    wa_msg_id = data.get("messages", [{}])[0].get("id")
        except Exception as e:
            logger.error(f"WhatsApp send error: {e}")

    direction = MessageDirection.note if req.is_note else MessageDirection.outbound
    msg_type = MessageType.note if req.is_note else MessageType.text

    message = Message(
        conversation_id=conv.id,
        whatsapp_message_id=wa_msg_id,
        direction=direction,
        message_type=msg_type,
        body=req.message,
        status=MessageStatus.sent,
        sender_id=current_user.id,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(message)
    conv.last_message_at = datetime.now(timezone.utc)
    conv.last_message_preview = req.message[:200]
    db.commit()
    db.refresh(message)

    return {
        "id": message.id,
        "direction": message.direction,
        "message_type": message.message_type,
        "body": message.body,
        "status": message.status,
        "timestamp": message.timestamp.isoformat(),
        "created_at": message.created_at.isoformat(),
    }


# ─── Send Media ──────────────────────────────────────────────────────────

@router.post("/send-media")
async def send_media(
    conversation_id: str = Form(...),
    caption: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")

    line = db.query(WhatsAppLine).filter(WhatsAppLine.id == conv.whatsapp_line_id).first()

    # Save file locally
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    saved_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, saved_name)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    mime = file.content_type or "application/octet-stream"
    media_type = "image" if mime.startswith("image/") else "document"

    wa_media_id = None
    wa_msg_id = None

    valid_phone_id = (
        WHATSAPP_ACCESS_TOKEN and line and
        line.phone_number_id and
        line.phone_number_id.isdigit()  # Meta phone_number_ids are always numeric
    )
    if valid_phone_id:
        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Upload media to Meta.
                # All fields (including text ones) must go in `files` as (None, value)
                # tuples — mixing `files` + `data` causes httpx to malform the boundary.
                upload_resp = await client.post(
                    f"{WHATSAPP_GRAPH_URL}/{line.phone_number_id}/media",
                    headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"},
                    files={
                        "file": (file.filename or "upload", content, mime),
                        "messaging_product": (None, "whatsapp"),
                        "type": (None, mime),
                    },
                    timeout=30,
                )
                logger.info(f"Media upload status: {upload_resp.status_code} — {upload_resp.text[:200]}")
                if upload_resp.status_code == 200:
                    wa_media_id = upload_resp.json().get("id")
                else:
                    logger.error(f"Media upload failed: {upload_resp.status_code} {upload_resp.text}")

                if wa_media_id:
                    # Step 2: Send the message using the uploaded media ID
                    # (must be inside the same `async with` block — client closes on exit)
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": conv.customer_whatsapp_id,
                        "type": media_type,
                        media_type: {"id": wa_media_id, "caption": caption},
                    }
                    send_resp = await client.post(
                        f"{WHATSAPP_GRAPH_URL}/{line.phone_number_id}/messages",
                        headers={
                            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=15,
                    )
                    logger.info(f"Media message send status: {send_resp.status_code} — {send_resp.text[:200]}")
                    if send_resp.status_code == 200:
                        wa_msg_id = send_resp.json().get("messages", [{}])[0].get("id")
                    else:
                        logger.error(f"Media message send failed: {send_resp.status_code} {send_resp.text}")
        except Exception as e:
            logger.error(f"WhatsApp media send error: {e}")
    else:
        logger.warning(f"Skipping WhatsApp send — invalid phone_number_id: {line.phone_number_id if line else 'no line'}")

    # Determine send success
    wa_send_ok = wa_msg_id is not None
    send_status = MessageStatus.sent if wa_send_ok else MessageStatus.failed

    mf = MediaFile(
        whatsapp_media_id=wa_media_id,
        conversation_id=conv.id,
        file_name=saved_name,
        original_name=file.filename,
        mime_type=mime,
        file_size=len(content),
        storage_path=file_path,
        media_type=media_type,
        caption=caption,
    )
    db.add(mf)
    db.flush()

    msg = Message(
        conversation_id=conv.id,
        whatsapp_message_id=wa_msg_id,
        direction=MessageDirection.outbound,
        message_type=MessageType(media_type),
        body=caption or file.filename,
        status=send_status,
        sender_id=current_user.id,
        media_file_id=mf.id,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)
    conv.last_message_preview = f"[{media_type}] {file.filename}"
    db.commit()

    if not wa_send_ok:
        logger.warning(f"Media file saved locally but WhatsApp delivery failed for conv {conv.id}")

    return {"ok": True, "wa_sent": wa_send_ok, "media_url": f"/api/media/files/{mf.id}"}


# ─── Media serve ─────────────────────────────────────────────────────────

@router.get("/media/{media_id}")
async def get_media(media_id: str, db: Session = Depends(get_db)):
    """Proxy/fetch WhatsApp media by WhatsApp media ID."""
    if not WHATSAPP_ACCESS_TOKEN:
        raise HTTPException(404, "No access token")
    try:
        async with httpx.AsyncClient() as client:
            meta_resp = await client.get(
                f"{WHATSAPP_GRAPH_URL}/{media_id}",
                headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"},
                timeout=10,
            )
            if meta_resp.status_code != 200:
                raise HTTPException(404, "Media not found")
            url = meta_resp.json().get("url")
            media_resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"},
                timeout=30,
            )
            from fastapi.responses import Response
            return Response(
                content=media_resp.content,
                media_type=meta_resp.json().get("mime_type", "application/octet-stream"),
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
