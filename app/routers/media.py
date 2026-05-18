import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.whatsapp import MediaFile
from app.models.patient import PatientDocument

router = APIRouter(prefix="/api/media", tags=["media"])


def _file_response(path: str, mime: str, name: str) -> FileResponse:
    """Return a FileResponse that displays images inline and downloads other types."""
    mime = mime or "application/octet-stream"
    is_image = mime.startswith("image/")
    if is_image:
        # No filename → browser shows inline (no download prompt)
        return FileResponse(path, media_type=mime)
    else:
        return FileResponse(path, media_type=mime, filename=name)


@router.get("/files/{file_id}")
def serve_media_file(file_id: str, db: Session = Depends(get_db)):
    """Serve locally stored media files (no auth required — used by <img> tags)."""
    # Check MediaFile
    mf = db.query(MediaFile).filter(MediaFile.id == file_id).first()
    if mf and mf.storage_path and os.path.exists(mf.storage_path):
        return _file_response(mf.storage_path, mf.mime_type, mf.original_name or mf.file_name)

    # Check PatientDocument
    doc = db.query(PatientDocument).filter(PatientDocument.id == file_id).first()
    if doc and doc.storage_path and os.path.exists(doc.storage_path):
        return _file_response(doc.storage_path, doc.mime_type, doc.original_name or doc.file_name)

    raise HTTPException(404, "File not found")
