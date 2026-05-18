"""
Patient Portal API
Endpoints are public (doctors list) or protected by a portal-specific JWT.
Auth uses 6-digit OTP sent to the patient's registered email via Resend.
Supports both login (existing patients) and registration (new patients).
"""
import json
import random
import string
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models.patient import Patient, PatientDocument, PatientStatus
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.clinic import Clinic
from app.models.portal import PatientPortalOTP
from app.config import (
    SECRET_KEY, ALGORITHM,
    RESEND_API_KEY, PORTAL_FROM_EMAIL, PORTAL_BASE_URL,
)

router = APIRouter(prefix="/api/portal", tags=["portal"])
logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)

PORTAL_TOKEN_EXPIRE_DAYS = 7


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def _create_portal_token(patient_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=PORTAL_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": patient_id, "type": "portal", "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def get_portal_patient(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> Patient:
    if not credentials:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "portal":
            raise HTTPException(401, "Invalid token type")
        patient_id = payload.get("sub")
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(401, "Patient account not found")
    return patient


def _invalidate_old_otps(identifier: str, db: Session):
    """Mark any unused OTPs for this email as used before issuing a new one."""
    db.query(PatientPortalOTP).filter(
        PatientPortalOTP.identifier == identifier,
        PatientPortalOTP.used == False,
    ).update({"used": True})
    db.commit()


async def _send_otp_email(to_email: str, first_name: str, code: str, purpose: str = "login"):
    """Send OTP via Resend. Falls back to logging when no API key is set (dev mode)."""
    action_text = "sign in to" if purpose == "login" else "verify your email for"
    subject = f"{code} — Your TMASI Portal {'Login' if purpose == 'login' else 'Verification'} Code"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:'Segoe UI',Arial,sans-serif;background:#f0f9ff;margin:0;padding:40px 20px;">
      <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:16px;
                  box-shadow:0 4px 24px rgba(8,145,178,.1);overflow:hidden;">
        <div style="background:linear-gradient(135deg,#0891b2,#0e7490);padding:32px;text-align:center;">
          <div style="font-size:32px;margin-bottom:8px;">⚕</div>
          <h1 style="color:#fff;margin:0;font-size:22px;font-weight:700;">TMASI Medical Centre</h1>
          <p style="color:#bae6fd;margin:6px 0 0;font-size:13px;">Patient Portal</p>
        </div>
        <div style="padding:36px 32px;">
          <p style="color:#334155;font-size:16px;margin:0 0 8px;font-weight:600;">Hello, {first_name}!</p>
          <p style="color:#64748b;font-size:14px;margin:0 0 28px;line-height:1.6;">
            Use the code below to {action_text} your TMASI Patient Portal.
            This code expires in <strong>10 minutes</strong> and can only be used once.
          </p>
          <div style="background:#f0f9ff;border:2px dashed #06b6d4;border-radius:12px;
                      padding:28px;text-align:center;margin-bottom:28px;">
            <div style="font-size:46px;font-weight:900;letter-spacing:14px;
                        color:#0891b2;font-family:monospace;line-height:1;">{code}</div>
          </div>
          {"<p style='background:#fef3c7;border-left:4px solid #f59e0b;border-radius:6px;padding:12px 16px;font-size:13px;color:#92400e;margin-bottom:0'>If you didn't request this code, you can safely ignore this email. Your account has not been created.</p>" if purpose == "register" else ""}
          {"<p style='font-size:13px;color:#94a3b8;margin:16px 0 0;text-align:center'>If you didn't request this, you can safely ignore this email.</p>" if purpose == "login" else ""}
        </div>
        <div style="background:#f8fafc;padding:16px 32px;text-align:center;border-top:1px solid #e2e8f0;">
          <p style="color:#94a3b8;font-size:12px;margin:0;">
            &copy; 2025 TMASI Medical Centre &nbsp;&middot;&nbsp; All rights reserved
          </p>
        </div>
      </div>
    </body>
    </html>
    """

    if not RESEND_API_KEY:
        logger.info(f"[DEV — no Resend key] OTP for {to_email} ({purpose}): {code}")
        return

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from": PORTAL_FROM_EMAIL,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body,
                },
                timeout=10,
            )
            if resp.status_code not in (200, 201):
                logger.error(f"Resend error {resp.status_code}: {resp.text[:300]}")
            else:
                logger.info(f"OTP email sent to {to_email} [{purpose}] via Resend")
    except Exception as e:
        logger.error(f"Failed to send OTP email: {e}")


def _patient_to_dict(p: Patient) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "email": p.email,
        "phone": p.phone,
        "country": p.country,
        "city": p.city,
        "service_type": p.service_type,
        "status": p.status,
        "created_at": p.created_at.isoformat(),
    }


# ─── Public endpoints ──────────────────────────────────────────────────────────

@router.get("/doctors")
def list_portal_doctors(db: Session = Depends(get_db)):
    """Public doctor listing for the portal landing page."""
    from sqlalchemy import or_
    doctors = db.query(Doctor).filter(
        Doctor.is_active == True,
        or_(Doctor.available_on_portal == True, Doctor.available_on_portal.is_(None)),
    ).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "specialty": d.specialty,
            "bio": d.bio,
            "photo_url": d.photo_url,
            "languages": d.languages,
            "consultation_fee_note": d.consultation_fee_note,
            "clinic_name": d.clinic.name if d.clinic else None,
        }
        for d in doctors
    ]


@router.get("/clinic")
def get_clinic_info(db: Session = Depends(get_db)):
    clinic = db.query(Clinic).filter(Clinic.is_active == True).first()
    if not clinic:
        return {}
    return {
        "name": clinic.name,
        "address": clinic.address,
        "city": clinic.city,
        "country": clinic.country,
        "phone": clinic.phone,
        "email": clinic.email,
        "specialties": clinic.specialties,
    }


# ─── Auth: Login (existing patients) ──────────────────────────────────────────

class OTPRequest(BaseModel):
    identifier: str  # email or phone


@router.post("/auth/request-otp")
async def request_login_otp(req: OTPRequest, db: Session = Depends(get_db)):
    """Send a login OTP to an existing patient's email."""
    identifier = req.identifier.strip().lower()

    # Resolve patient by email
    patient = db.query(Patient).filter(Patient.email == identifier).first()
    if not patient:
        # Try by phone (strip formatting)
        clean_req = identifier.replace(" ", "").replace("-", "").replace("+", "")
        for p in db.query(Patient).filter(Patient.phone.isnot(None)).all():
            if (p.phone or "").replace(" ", "").replace("-", "").replace("+", "") == clean_req:
                patient = p
                break

    # Always return 200 to avoid revealing whether the account exists
    if not patient:
        logger.info(f"Login OTP for unknown identifier: {identifier}")
        return {"ok": True, "message": "If an account exists, a code has been sent."}

    if not patient.email:
        raise HTTPException(
            400,
            "No email address on file. Please contact us via WhatsApp to add your email first."
        )

    _invalidate_old_otps(identifier, db)
    code = _generate_otp()
    otp = PatientPortalOTP(
        identifier=identifier,
        patient_id=patient.id,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        purpose="login",
    )
    db.add(otp)
    db.commit()

    await _send_otp_email(patient.email, patient.name.split()[0], code, purpose="login")
    return {"ok": True, "message": "If an account exists, a code has been sent."}


# ─── Auth: Registration (new patients) ────────────────────────────────────────

class RegisterRequest(BaseModel):
    full_name: str
    email: str
    phone: str
    country: Optional[str] = None
    city: Optional[str] = None
    service_type: Optional[str] = None


@router.post("/auth/register")
async def register_patient(req: RegisterRequest, db: Session = Depends(get_db)):
    """
    Step 1 of registration: validate form data, check for duplicates,
    send email verification OTP.
    """
    # Validate required fields
    name = req.full_name.strip()
    email = req.email.strip().lower()
    phone = req.phone.strip()

    if not name or len(name) < 2:
        raise HTTPException(400, "Please enter your full name (at least 2 characters).")
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Please enter a valid email address.")
    if not phone or len(phone.replace(" ", "").replace("+", "").replace("-", "")) < 7:
        raise HTTPException(400, "Please enter a valid phone number.")

    # Check if email already registered
    existing = db.query(Patient).filter(Patient.email == email).first()
    if existing:
        raise HTTPException(
            409,
            "An account with this email already exists. Please sign in instead."
        )

    # Invalidate any previous OTPs for this email
    _invalidate_old_otps(email, db)

    # Store registration data as JSON in the OTP record
    pending = {
        "full_name": name,
        "phone": phone,
        "country": req.country or "",
        "city": req.city or "",
        "service_type": req.service_type or "",
    }

    code = _generate_otp()
    otp = PatientPortalOTP(
        identifier=email,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        purpose="register",
        pending_data=json.dumps(pending),
    )
    db.add(otp)
    db.commit()

    first_name = name.split()[0]
    await _send_otp_email(email, first_name, code, purpose="register")
    return {"ok": True, "message": "Verification code sent. Please check your email."}


# ─── Auth: Verify OTP (shared by login and register) ──────────────────────────

class OTPVerify(BaseModel):
    identifier: str
    code: str


@router.post("/auth/verify-otp")
def verify_otp(req: OTPVerify, db: Session = Depends(get_db)):
    """
    Step 2 of both login and registration.
    - login:    finds existing patient, returns JWT
    - register: creates patient from pending_data, returns JWT
    """
    identifier = req.identifier.strip().lower()
    code = req.code.strip()

    otp = (
        db.query(PatientPortalOTP)
        .filter(
            PatientPortalOTP.identifier == identifier,
            PatientPortalOTP.code == code,
            PatientPortalOTP.used == False,
        )
        .order_by(PatientPortalOTP.created_at.desc())
        .first()
    )

    if not otp:
        raise HTTPException(400, "Invalid code. Please check your email and try again.")

    # Normalize expires_at to UTC-aware for comparison
    expires = otp.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise HTTPException(400, "This code has expired. Please request a new one.")

    # Mark used immediately to prevent replay
    otp.used = True
    db.flush()

    # ── Login path ────────────────────────────────────────────────────────────
    if otp.purpose == "login":
        patient = db.query(Patient).filter(Patient.id == otp.patient_id).first()
        if not patient:
            db.rollback()
            raise HTTPException(404, "Patient account not found. Please register first.")
        db.commit()
        return {
            "access_token": _create_portal_token(patient.id),
            "token_type": "bearer",
            "is_new": False,
            "patient": _patient_to_dict(patient),
        }

    # ── Register path ─────────────────────────────────────────────────────────
    if otp.purpose == "register":
        if not otp.pending_data:
            db.rollback()
            raise HTTPException(400, "Registration data missing. Please start over.")

        try:
            data = json.loads(otp.pending_data)
        except Exception:
            db.rollback()
            raise HTTPException(400, "Registration data corrupted. Please start over.")

        # Final duplicate check (race condition guard)
        if db.query(Patient).filter(Patient.email == identifier).first():
            db.rollback()
            raise HTTPException(
                409,
                "An account with this email was just created. Please sign in instead."
            )

        patient = Patient(
            name=data["full_name"],
            email=identifier,
            phone=data["phone"],
            country=data.get("country") or None,
            city=data.get("city") or None,
            service_type=data.get("service_type") or None,
            status=PatientStatus.new,
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

        logger.info(f"New patient registered via portal: {patient.name} ({identifier})")
        return {
            "access_token": _create_portal_token(patient.id),
            "token_type": "bearer",
            "is_new": True,
            "patient": _patient_to_dict(patient),
        }

    db.rollback()
    raise HTTPException(400, "Unknown OTP purpose. Please start over.")


# ─── Authenticated patient endpoints ──────────────────────────────────────────

@router.get("/me")
def get_me(patient: Patient = Depends(get_portal_patient)):
    return _patient_to_dict(patient)


@router.get("/appointments")
def get_my_appointments(
    patient: Patient = Depends(get_portal_patient),
    db: Session = Depends(get_db),
):
    appts = (
        db.query(Appointment)
        .filter(Appointment.patient_id == patient.id)
        .order_by(Appointment.appointment_date.desc())
        .all()
    )
    result = []
    for a in appts:
        result.append({
            "id": a.id,
            "title": a.title,
            "appointment_date": a.appointment_date.isoformat(),
            "end_date": a.end_date.isoformat() if a.end_date else None,
            "status": a.status,
            "service_type": a.service_type,
            "notes": a.notes,
            "doctor_name": a.doctor.name if a.doctor else None,
            "doctor_specialty": a.doctor.specialty if a.doctor else None,
            "clinic_name": a.clinic.name if a.clinic else None,
        })
    return result


@router.get("/documents")
def get_my_documents(
    patient: Patient = Depends(get_portal_patient),
    db: Session = Depends(get_db),
):
    docs = (
        db.query(PatientDocument)
        .filter(PatientDocument.patient_id == patient.id)
        .order_by(PatientDocument.created_at.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "name": d.original_name or d.file_name,
            "mime_type": d.mime_type,
            "description": d.description,
            "created_at": d.created_at.isoformat(),
            "url": f"/api/media/files/{d.id}",
        }
        for d in docs
    ]


class BookingRequest(BaseModel):
    doctor_id: Optional[str] = None
    service_type: Optional[str] = None
    preferred_date: Optional[str] = None
    notes: Optional[str] = None


@router.post("/appointments/request")
def request_appointment(
    req: BookingRequest,
    patient: Patient = Depends(get_portal_patient),
    db: Session = Depends(get_db),
):
    from app.models.appointment import AppointmentStatus

    doctor = None
    clinic = None
    if req.doctor_id:
        doctor = db.query(Doctor).filter(Doctor.id == req.doctor_id).first()
        if doctor and doctor.clinic_id:
            clinic = db.query(Clinic).filter(Clinic.id == doctor.clinic_id).first()

    appt_date = datetime.now(timezone.utc)
    if req.preferred_date:
        try:
            appt_date = datetime.fromisoformat(req.preferred_date.replace("Z", "+00:00"))
        except Exception:
            pass

    title = f"Appointment Request — {req.service_type or (doctor.specialty if doctor else 'General Consultation')}"
    appt = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id if doctor else None,
        clinic_id=clinic.id if clinic else None,
        title=title,
        appointment_date=appt_date,
        status=AppointmentStatus.scheduled,
        service_type=req.service_type,
        notes=req.notes,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    return {
        "ok": True,
        "appointment_id": appt.id,
        "message": "Your appointment request has been received. Our team will confirm shortly via WhatsApp or email.",
    }
