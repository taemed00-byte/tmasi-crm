"""Case Document upload and retrieval."""
import os, uuid, shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone
from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.models.case import Case
from app.models.document import CaseDocument, DocumentType

router = APIRouter(prefix="/api/documents", tags=["documents"])

UPLOAD_DIR = "uploads/documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_MIME = {
    "application/pdf", "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
}
MAX_SIZE_MB = 20


def _doc_dict(d: CaseDocument) -> dict:
    return {
        "id": d.id, "case_id": d.case_id,
        "doc_type": d.doc_type.value if d.doc_type else None,
        "filename": d.filename,
        "file_size": d.file_size,
        "mime_type": d.mime_type,
        "description": d.description,
        "is_latest": d.is_latest,
        "version": d.version,
        "uploaded_by": d.uploaded_by,
        "uploader_name": d.uploader.full_name if d.uploader else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "download_url": f"/api/documents/{d.id}/download",
    }


@router.get("/case/{case_id}")
def list_case_documents(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    docs = db.query(CaseDocument).filter(
        CaseDocument.case_id == case_id
    ).order_by(CaseDocument.created_at.desc()).all()
    return [_doc_dict(d) for d in docs]


@router.post("/case/{case_id}")
async def upload_document(
    case_id: str,
    file: UploadFile = File(...),
    doc_type: str = Form("other"),
    description: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Validate size
    contents = await file.read()
    if len(contents) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_SIZE_MB}MB limit")

    # Validate type
    mime = file.content_type or "application/octet-stream"

    # Validate doc_type enum
    try:
        doc_type_enum = DocumentType(doc_type)
    except ValueError:
        doc_type_enum = DocumentType.other

    # Mark old versions as not latest
    db.query(CaseDocument).filter(
        CaseDocument.case_id == case_id,
        CaseDocument.doc_type == doc_type_enum,
        CaseDocument.is_latest == True,
    ).update({"is_latest": False})

    # Determine version
    version = db.query(CaseDocument).filter(
        CaseDocument.case_id == case_id,
        CaseDocument.doc_type == doc_type_enum,
    ).count() + 1

    # Save file
    ext = os.path.splitext(file.filename or "file")[1]
    stored_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, stored_name)
    with open(file_path, "wb") as f:
        f.write(contents)

    doc = CaseDocument(
        case_id=case_id,
        uploaded_by=current_user.id,
        doc_type=doc_type_enum,
        filename=file.filename or stored_name,
        file_path=file_path,
        file_size=len(contents),
        mime_type=mime,
        description=description,
        is_latest=True,
        version=version,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _doc_dict(doc)


@router.get("/{doc_id}/download")
def download_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(CaseDocument).filter(CaseDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        path=doc.file_path,
        filename=doc.filename,
        media_type=doc.mime_type or "application/octet-stream",
    )


@router.delete("/{doc_id}")
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(CaseDocument).filter(CaseDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # Remove file from disk
    try:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except Exception:
        pass
    db.delete(doc)
    db.commit()
    return {"ok": True}
