import os
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.models.patient import Patient, PatientDocument
from app.models.whatsapp import Conversation, MediaFile
from app.config import UPLOAD_DIR
from pydantic import BaseModel

router = APIRouter(prefix="/api/patients", tags=["patients"])
logger = logging.getLogger(__name__)


class PatientCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    location: Optional[str] = None
    service_type: Optional[str] = None
    request_details: Optional[str] = None
    priority: Optional[str] = "normal"
    status: Optional[str] = "new"
    conversation_id: Optional[str] = None  # link to conversation


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    location: Optional[str] = None
    service_type: Optional[str] = None
    request_details: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None


def patient_to_dict(p: Patient, db: Session) -> dict:
    docs = [{"id": d.id, "file_name": d.file_name, "original_name": d.original_name, "mime_type": d.mime_type, "url": f"/api/media/files/{d.id}"} for d in p.documents]
    media = [{"id": m.id, "file_name": m.file_name, "original_name": m.original_name, "mime_type": m.mime_type, "media_type": m.media_type, "url": f"/api/media/{m.id}" if not m.storage_path else f"/api/media/files/{m.id}"} for m in p.media_files]
    convs = [{"id": c.id, "whatsapp_line_id": c.whatsapp_line_id, "customer_whatsapp_id": c.customer_whatsapp_id, "status": c.status, "last_message_preview": c.last_message_preview, "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None} for c in p.conversations]
    appts = [{"id": a.id, "title": a.title, "appointment_date": a.appointment_date.isoformat(), "status": a.status, "doctor_id": a.doctor_id, "clinic_id": a.clinic_id} for a in p.appointments]
    return {
        "id": p.id, "name": p.name, "phone": p.phone, "email": p.email,
        "country": p.country, "city": p.city, "location": p.location,
        "service_type": p.service_type, "request_details": p.request_details,
        "priority": p.priority, "status": p.status,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
        "documents": docs, "media_files": media,
        "conversations": convs, "appointments": appts,
    }


@router.get("")
def list_patients(
    search: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Patient)
    if search:
        q = q.filter(
            Patient.name.ilike(f"%{search}%") |
            Patient.phone.ilike(f"%{search}%") |
            Patient.email.ilike(f"%{search}%")
        )
    if status:
        q = q.filter(Patient.status == status)
    q = q.order_by(Patient.updated_at.desc())
    total = q.count()
    patients = q.offset(offset).limit(limit).all()
    return {"total": total, "items": [patient_to_dict(p, db) for p in patients]}


@router.post("")
def create_patient(req: PatientCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    patient = Patient(
        name=req.name, phone=req.phone, email=req.email,
        country=req.country, city=req.city, location=req.location,
        service_type=req.service_type, request_details=req.request_details,
        priority=req.priority or "normal", status=req.status or "new",
        created_by=current_user.id,
    )
    db.add(patient)
    db.flush()

    # Link conversation if provided
    if req.conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == req.conversation_id).first()
        if conv:
            conv.patient_id = patient.id
            # Also link any media from that conversation
            for mf in db.query(MediaFile).filter(MediaFile.conversation_id == conv.id).all():
                if not mf.patient_id:
                    mf.patient_id = patient.id

    db.commit()
    db.refresh(patient)
    return patient_to_dict(patient, db)


@router.get("/{patient_id}")
def get_patient(patient_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(404, "Patient not found")
    return patient_to_dict(p, db)


@router.patch("/{patient_id}")
def update_patient(patient_id: str, req: PatientUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(404, "Patient not found")
    for field, val in req.dict(exclude_unset=True).items():
        if val is not None:
            setattr(p, field, val)
    db.commit()
    db.refresh(p)
    return patient_to_dict(p, db)


@router.post("/{patient_id}/documents")
async def upload_patient_document(
    patient_id: str,
    file: UploadFile = File(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(404, "Patient not found")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    saved_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, saved_name)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc = PatientDocument(
        patient_id=patient_id,
        file_name=saved_name,
        original_name=file.filename,
        mime_type=file.content_type,
        file_size=len(content),
        storage_path=file_path,
        description=description,
        uploaded_by=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "file_name": doc.file_name, "original_name": doc.original_name, "url": f"/api/media/files/{doc.id}"}


class SyncMediaRequest(BaseModel):
    conversation_id: str


@router.post("/{patient_id}/sync-media")
def sync_patient_media(
    patient_id: str,
    req: SyncMediaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Link all unlinked media files from a conversation to an existing patient."""
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(404, "Patient not found")
    conv = db.query(Conversation).filter(Conversation.id == req.conversation_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    # Ensure conversation is linked to this patient
    if conv.patient_id != patient_id:
        conv.patient_id = patient_id
    # Link any media from that conversation that isn't already linked
    linked = 0
    for mf in db.query(MediaFile).filter(MediaFile.conversation_id == conv.id).all():
        if not mf.patient_id:
            mf.patient_id = patient_id
            linked += 1
    db.commit()
    db.refresh(p)
    return {"ok": True, "linked": linked, "patient": patient_to_dict(p, db)}


@router.delete("/{patient_id}/documents/{doc_id}")
def delete_patient_document(patient_id: str, doc_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(PatientDocument).filter(PatientDocument.id == doc_id, PatientDocument.patient_id == patient_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc.storage_path and os.path.exists(doc.storage_path):
        os.remove(doc.storage_path)
    db.delete(doc)
    db.commit()
    return {"ok": True}
