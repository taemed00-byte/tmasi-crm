from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.models.doctor import Doctor
from pydantic import BaseModel

router = APIRouter(prefix="/api/doctors", tags=["doctors"])


class DoctorCreate(BaseModel):
    name: str
    specialty: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    clinic_id: Optional[str] = None
    bio: Optional[str] = None


class DoctorUpdate(BaseModel):
    name: Optional[str] = None
    specialty: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    clinic_id: Optional[str] = None
    bio: Optional[str] = None
    is_active: Optional[bool] = None


def doctor_dict(d: Doctor) -> dict:
    return {
        "id": d.id, "name": d.name, "specialty": d.specialty,
        "phone": d.phone, "email": d.email, "clinic_id": d.clinic_id,
        "clinic_name": d.clinic.name if d.clinic else None,
        "bio": d.bio, "is_active": d.is_active,
        "created_at": d.created_at.isoformat(),
    }


@router.get("")
def list_doctors(search: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(Doctor).filter(Doctor.is_active == True)
    if search:
        q = q.filter(Doctor.name.ilike(f"%{search}%") | Doctor.specialty.ilike(f"%{search}%"))
    return [doctor_dict(d) for d in q.order_by(Doctor.name).all()]


@router.post("")
def create_doctor(req: DoctorCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    d = Doctor(**req.dict())
    db.add(d)
    db.commit()
    db.refresh(d)
    return doctor_dict(d)


@router.get("/{doctor_id}")
def get_doctor(doctor_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    d = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not d:
        raise HTTPException(404, "Doctor not found")
    return doctor_dict(d)


@router.patch("/{doctor_id}")
def update_doctor(doctor_id: str, req: DoctorUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    d = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not d:
        raise HTTPException(404, "Doctor not found")
    for k, v in req.dict(exclude_unset=True).items():
        setattr(d, k, v)
    db.commit()
    db.refresh(d)
    return doctor_dict(d)


@router.delete("/{doctor_id}")
def delete_doctor(doctor_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    d = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not d:
        raise HTTPException(404, "Doctor not found")
    d.is_active = False
    db.commit()
    return {"ok": True}
