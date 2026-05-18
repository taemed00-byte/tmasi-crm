from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.models.clinic import Clinic
from pydantic import BaseModel

router = APIRouter(prefix="/api/clinics", tags=["clinics"])


class ClinicCreate(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    specialties: Optional[str] = None


class ClinicUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    specialties: Optional[str] = None
    is_active: Optional[bool] = None


def clinic_dict(c: Clinic) -> dict:
    return {
        "id": c.id, "name": c.name, "address": c.address,
        "city": c.city, "country": c.country, "phone": c.phone,
        "email": c.email, "specialties": c.specialties, "is_active": c.is_active,
        "created_at": c.created_at.isoformat(),
        "doctor_count": len([d for d in c.doctors if d.is_active]),
    }


@router.get("")
def list_clinics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return [clinic_dict(c) for c in db.query(Clinic).filter(Clinic.is_active == True).order_by(Clinic.name).all()]


@router.post("")
def create_clinic(req: ClinicCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = Clinic(**req.dict())
    db.add(c)
    db.commit()
    db.refresh(c)
    return clinic_dict(c)


@router.get("/{clinic_id}")
def get_clinic(clinic_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not c:
        raise HTTPException(404, "Clinic not found")
    return clinic_dict(c)


@router.patch("/{clinic_id}")
def update_clinic(clinic_id: str, req: ClinicUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not c:
        raise HTTPException(404, "Clinic not found")
    for k, v in req.dict(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return clinic_dict(c)


@router.delete("/{clinic_id}")
def delete_clinic(clinic_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not c:
        raise HTTPException(404, "Not found")
    c.is_active = False
    db.commit()
    return {"ok": True}
