"""Case Management Engine router."""
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from app.models.case import OPEN_STATUSES, CLOSED_STATUSES
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from app.database import get_db
from app.auth import get_current_user
from app.models.user import User, UserRole
from app.models.case import (
    Case, CaseNote, CaseTask, CaseEscalation,
    CaseStatus, CasePriority, CaseType, NoteType, TaskStatus,
)
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.clinic import Clinic

router = APIRouter(prefix="/api/cases", tags=["cases"])


# --- Helpers -----------------------------------------------------------------

def _next_case_number(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"CRM-{year}-"
    last = (
        db.query(Case.case_number)
        .filter(Case.case_number.like(f"{prefix}%"))
        .order_by(Case.case_number.desc())
        .first()
    )
    if last:
        try:
            seq = int(last[0].split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:05d}"


def _sla_due(hours: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _require_admin_or_manager(user: User):
    if user.role not in (UserRole.super_admin, UserRole.clinic_admin, UserRole.case_manager):
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def _case_to_dict(c: Case, include_notes: bool = False) -> dict:
    d = {
        "id": c.id,
        "case_number": c.case_number,
        "patient_id": c.patient_id,
        "patient_name": c.patient.name if c.patient else None,
        "patient_phone": c.patient.phone if c.patient else None,
        "assigned_to": c.assigned_to,
        "assignee_name": c.assignee.full_name if c.assignee else None,
        "doctor_id": c.doctor_id,
        "doctor_name": c.doctor.name if c.doctor else None,
        "clinic_id": c.clinic_id,
        "clinic_name": c.clinic.name if c.clinic else None,
        "type": c.type,
        "status": c.status,
        "priority": c.priority,
        "title": c.title,
        "description": c.description,
        "service_type": c.service_type,
        "country_of_origin": c.country_of_origin,
        "treatment_country": c.treatment_country,
        "estimated_cost": c.estimated_cost,
        "currency": c.currency,
        "insurance_provider": c.insurance_provider,
        "insurance_policy_number": c.insurance_policy_number,
        "insurance_pre_auth": c.insurance_pre_auth,
        "sla_hours": c.sla_hours,
        "sla_due_at": c.sla_due_at.isoformat() if c.sla_due_at else None,
        "sla_breached": c.sla_breached,
        "opened_at": c.opened_at.isoformat() if c.opened_at else None,
        "closed_at": c.closed_at.isoformat() if c.closed_at else None,
        "created_by": c.created_by,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "tasks_total": len(c.tasks) if c.tasks is not None else 0,
        "tasks_done": sum(1 for t in c.tasks if t.status == TaskStatus.done) if c.tasks else 0,
    }
    if include_notes:
        d["notes"] = [_note_to_dict(n) for n in (c.notes or [])]
        d["tasks"] = [_task_to_dict(t) for t in (c.tasks or [])]
        d["escalations"] = [_escalation_to_dict(e) for e in (c.escalations or [])]
    return d


def _note_to_dict(n: CaseNote) -> dict:
    return {
        "id": n.id,
        "case_id": n.case_id,
        "author_id": n.author_id,
        "author_name": n.author.full_name if n.author else "System",
        "body": n.body,
        "note_type": n.note_type,
        "is_internal": n.is_internal,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


def _task_to_dict(t: CaseTask) -> dict:
    return {
        "id": t.id,
        "case_id": t.case_id,
        "assigned_to": t.assigned_to,
        "assignee_name": t.assignee.full_name if t.assignee else None,
        "title": t.title,
        "description": t.description,
        "due_at": t.due_at.isoformat() if t.due_at else None,
        "status": t.status,
        "completed_by": t.completed_by,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _escalation_to_dict(e: CaseEscalation) -> dict:
    return {
        "id": e.id,
        "case_id": e.case_id,
        "escalated_by": e.escalated_by,
        "by_name": e.by_user.full_name if e.by_user else None,
        "escalated_to": e.escalated_to,
        "to_name": e.to_user.full_name if e.to_user else None,
        "reason": e.reason,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


# --- Pydantic schemas --------------------------------------------------------

class CaseCreate(BaseModel):
    patient_id: str
    title: str
    type: CaseType = CaseType.international_care
    priority: CasePriority = CasePriority.normal
    description: Optional[str] = None
    service_type: Optional[str] = None
    country_of_origin: Optional[str] = None
    treatment_country: Optional[str] = None
    assigned_to: Optional[str] = None
    doctor_id: Optional[str] = None
    clinic_id: Optional[str] = None
    estimated_cost: Optional[float] = None
    currency: Optional[str] = "USD"
    insurance_provider: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    insurance_pre_auth: Optional[bool] = False
    sla_hours: Optional[int] = 24


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[CaseType] = None
    priority: Optional[CasePriority] = None
    description: Optional[str] = None
    service_type: Optional[str] = None
    country_of_origin: Optional[str] = None
    treatment_country: Optional[str] = None
    assigned_to: Optional[str] = None
    doctor_id: Optional[str] = None
    clinic_id: Optional[str] = None
    estimated_cost: Optional[float] = None
    currency: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    insurance_pre_auth: Optional[bool] = None
    sla_hours: Optional[int] = None


class StatusTransition(BaseModel):
    status: CaseStatus
    note: Optional[str] = None


class NoteCreate(BaseModel):
    body: str
    note_type: NoteType = NoteType.general
    is_internal: bool = True


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    due_at: Optional[datetime] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    due_at: Optional[datetime] = None
    status: Optional[TaskStatus] = None


class EscalatePayload(BaseModel):
    escalated_to: Optional[str] = None
    reason: str


# --- Routes ------------------------------------------------------------------

_LOAD_OPTS = [
    joinedload(Case.patient),
    joinedload(Case.assignee),
    joinedload(Case.doctor),
    joinedload(Case.clinic),
    joinedload(Case.tasks),
]

_LOAD_FULL = [
    joinedload(Case.patient),
    joinedload(Case.assignee),
    joinedload(Case.doctor),
    joinedload(Case.clinic),
    joinedload(Case.notes).joinedload(CaseNote.author),
    joinedload(Case.tasks).joinedload(CaseTask.assignee),
    joinedload(Case.escalations).joinedload(CaseEscalation.by_user),
    joinedload(Case.escalations).joinedload(CaseEscalation.to_user),
]


@router.get("")
def list_cases(
    status_group: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Case).options(*_LOAD_OPTS)
    if status_group == "open":
        q = q.filter(Case.status.in_(OPEN_STATUSES))
    elif status_group == "closed":
        q = q.filter(Case.status.in_(CLOSED_STATUSES))
    if priority:
        q = q.filter(Case.priority == priority)
    if assigned_to:
        q = q.filter(Case.assigned_to == assigned_to)
    if patient_id:
        q = q.filter(Case.patient_id == patient_id)
    if search:
        term = f"%{search}%"
        q = q.join(Patient, Case.patient_id == Patient.id, isouter=True).filter(
            or_(
                Case.case_number.ilike(term),
                Case.title.ilike(term),
                Patient.name.ilike(term),
            )
        )
    total = q.count()
    cases = q.order_by(Case.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_case_to_dict(c) for c in cases]}


@router.post("", status_code=201)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    sla_hours = payload.sla_hours or 24
    case = Case(
        case_number=_next_case_number(db),
        patient_id=payload.patient_id,
        title=payload.title,
        type=payload.type,
        priority=payload.priority,
        description=payload.description,
        service_type=payload.service_type or patient.service_type,
        country_of_origin=payload.country_of_origin or patient.country,
        treatment_country=payload.treatment_country,
        assigned_to=payload.assigned_to,
        doctor_id=payload.doctor_id,
        clinic_id=payload.clinic_id,
        estimated_cost=payload.estimated_cost,
        currency=payload.currency or "USD",
        insurance_provider=payload.insurance_provider,
        insurance_policy_number=payload.insurance_policy_number,
        insurance_pre_auth=payload.insurance_pre_auth or False,
        sla_hours=sla_hours,
        sla_due_at=_sla_due(sla_hours),
        created_by=current_user.id,
    )
    db.add(case)
    db.flush()

    db.add(CaseNote(
        case_id=case.id,
        body=f"Case opened by {current_user.full_name or current_user.username}.",
        note_type=NoteType.system,
        is_internal=True,
    ))
    db.commit()
    db.refresh(case)

    case = db.query(Case).options(*_LOAD_FULL).filter(Case.id == case.id).first()
    return _case_to_dict(case, include_notes=True)


@router.get("/{case_id}")
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).options(*_LOAD_FULL).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return _case_to_dict(case, include_notes=True)


@router.put("/{case_id}")
def update_case(
    case_id: str,
    payload: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    update_data = payload.model_dump(exclude_none=True)
    if "sla_hours" in update_data:
        update_data["sla_due_at"] = _sla_due(update_data["sla_hours"])

    for field, value in update_data.items():
        setattr(case, field, value)
    db.commit()

    case = db.query(Case).options(*_LOAD_FULL).filter(Case.id == case_id).first()
    return _case_to_dict(case, include_notes=True)


@router.post("/{case_id}/status")
def transition_status(
    case_id: str,
    payload: StatusTransition,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    old_status = case.status
    case.status = payload.status
    if payload.status in (CaseStatus.closed, CaseStatus.cancelled):
        case.closed_at = datetime.now(timezone.utc)

    note_body = (
        f"Status changed from {old_status} to {payload.status} "
        f"by {current_user.full_name or current_user.username}."
    )
    if payload.note:
        note_body += f" Note: {payload.note}"
    db.add(CaseNote(case_id=case.id, body=note_body, note_type=NoteType.system, is_internal=True))
    db.commit()
    return {"status": case.status, "case_number": case.case_number}


@router.post("/{case_id}/assign")
def assign_case(
    case_id: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    user_id = body.get("user_id")
    assignee = None
    if user_id:
        assignee = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not assignee:
            raise HTTPException(status_code=404, detail="User not found")

    case.assigned_to = user_id
    label = (assignee.full_name or assignee.username) if assignee else "nobody"
    db.add(CaseNote(
        case_id=case.id,
        body=f"Case assigned to {label} by {current_user.full_name or current_user.username}.",
        note_type=NoteType.system,
        is_internal=True,
    ))
    db.commit()
    return {"assigned_to": case.assigned_to}


# --- Notes -------------------------------------------------------------------

@router.post("/{case_id}/notes", status_code=201)
def add_note(
    case_id: str,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not db.query(Case).filter(Case.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")

    note = CaseNote(
        case_id=case_id,
        author_id=current_user.id,
        body=payload.body,
        note_type=payload.note_type,
        is_internal=payload.is_internal,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    note = db.query(CaseNote).options(joinedload(CaseNote.author)).filter(CaseNote.id == note.id).first()
    return _note_to_dict(note)


@router.delete("/{case_id}/notes/{note_id}")
def delete_note(
    case_id: str,
    note_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.query(CaseNote).filter(CaseNote.id == note_id, CaseNote.case_id == case_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.author_id != current_user.id and current_user.role not in (UserRole.super_admin, UserRole.clinic_admin):
        raise HTTPException(status_code=403, detail="Cannot delete another user's note")
    db.delete(note)
    db.commit()
    return {"deleted": note_id}


# --- Tasks -------------------------------------------------------------------

@router.post("/{case_id}/tasks", status_code=201)
def add_task(
    case_id: str,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not db.query(Case).filter(Case.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")

    task = CaseTask(
        case_id=case_id,
        title=payload.title,
        description=payload.description,
        assigned_to=payload.assigned_to,
        due_at=payload.due_at,
        created_by=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    task = db.query(CaseTask).options(joinedload(CaseTask.assignee)).filter(CaseTask.id == task.id).first()
    return _task_to_dict(task)


@router.put("/{case_id}/tasks/{task_id}")
def update_task(
    case_id: str,
    task_id: str,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(CaseTask).filter(CaseTask.id == task_id, CaseTask.case_id == case_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = payload.model_dump(exclude_none=True)
    if update_data.get("status") == TaskStatus.done and not task.completed_at:
        update_data["completed_by"] = current_user.id
        update_data["completed_at"] = datetime.now(timezone.utc)

    for field, value in update_data.items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    task = db.query(CaseTask).options(joinedload(CaseTask.assignee)).filter(CaseTask.id == task.id).first()
    return _task_to_dict(task)


@router.delete("/{case_id}/tasks/{task_id}")
def delete_task(
    case_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(CaseTask).filter(CaseTask.id == task_id, CaseTask.case_id == case_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"deleted": task_id}


# --- Escalations -------------------------------------------------------------

@router.post("/{case_id}/escalate", status_code=201)
def escalate_case(
    case_id: str,
    payload: EscalatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    escalation = CaseEscalation(
        case_id=case_id,
        escalated_by=current_user.id,
        escalated_to=payload.escalated_to,
        reason=payload.reason,
    )
    db.add(escalation)

    if case.priority == CasePriority.normal:
        case.priority = CasePriority.high
    elif case.priority == CasePriority.high:
        case.priority = CasePriority.urgent

    db.add(CaseNote(
        case_id=case_id,
        body=f"ESCALATED by {current_user.full_name or current_user.username}: {payload.reason}",
        note_type=NoteType.escalation,
        is_internal=True,
    ))
    db.commit()
    return {"escalated": True, "new_priority": case.priority}
