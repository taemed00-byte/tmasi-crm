from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.models.appointment import Appointment
from pydantic import BaseModel

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


class AppointmentCreate(BaseModel):
    patient_id: str
    doctor_id: Optional[str] = None
    clinic_id: Optional[str] = None
    title: Optional[str] = None
    appointment_date: datetime
    end_date: Optional[datetime] = None
    status: Optional[str] = "scheduled"
    notes: Optional[str] = None
    service_type: Optional[str] = None


class AppointmentUpdate(BaseModel):
    doctor_id: Optional[str] = None
    clinic_id: Optional[str] = None
    title: Optional[str] = None
    appointment_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    service_type: Optional[str] = None


def appt_dict(a: Appointment) -> dict:
    return {
        "id": a.id,
        "patient_id": a.patient_id,
        "patient_name": a.patient.name if a.patient else None,
        "doctor_id": a.doctor_id,
        "doctor_name": a.doctor.name if a.doctor else None,
        "clinic_id": a.clinic_id,
        "clinic_name": a.clinic.name if a.clinic else None,
        "title": a.title,
        "appointment_date": a.appointment_date.isoformat(),
        "end_date": a.end_date.isoformat() if a.end_date else None,
        "status": a.status,
        "notes": a.notes,
        "service_type": a.service_type,
        "created_at": a.created_at.isoformat(),
    }


@router.get("")
def list_appointments(
    patient_id: Optional[str] = None,
    doctor_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Appointment)
    if patient_id:
        q = q.filter(Appointment.patient_id == patient_id)
    if doctor_id:
        q = q.filter(Appointment.doctor_id == doctor_id)
    if start_date:
        q = q.filter(Appointment.appointment_date >= datetime.fromisoformat(start_date))
    if end_date:
        q = q.filter(Appointment.appointment_date <= datetime.fromisoformat(end_date))
    return [appt_dict(a) for a in q.order_by(Appointment.appointment_date).all()]


@router.post("")
def create_appointment(req: AppointmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    a = Appointment(**req.dict(), created_by=current_user.id)
    db.add(a)
    db.commit()
    db.refresh(a)
    return appt_dict(a)


@router.get("/{appt_id}")
def get_appointment(appt_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    a = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not a:
        raise HTTPException(404, "Not found")
    return appt_dict(a)


@router.patch("/{appt_id}")
def update_appointment(appt_id: str, req: AppointmentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    a = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not a:
        raise HTTPException(404, "Not found")
    for k, v in req.dict(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return appt_dict(a)


@router.delete("/{appt_id}")
def delete_appointment(appt_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    a = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not a:
        raise HTTPException(404, "Not found")
    db.delete(a)
    db.commit()
    return {"ok": True}
