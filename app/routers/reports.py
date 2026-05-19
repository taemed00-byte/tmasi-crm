"""Reports & Analytics router."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Optional

from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.models.case import Case, CaseStatus, CasePriority, CaseType
from app.models.patient import Patient
from app.models.finance import Invoice, Payment, InvoiceStatus
from app.models.whatsapp import Conversation, Message, ConversationStatus
from app.models.appointment import Appointment, AppointmentStatus

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/dashboard")
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Main dashboard KPIs — single call for the dashboard page."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    # ── Cases ──────────────────────────────────────────────
    total_cases       = db.query(func.count(Case.id)).scalar() or 0
    open_cases        = db.query(func.count(Case.id)).filter(
        Case.status.notin_([CaseStatus.closed, CaseStatus.cancelled])
    ).scalar() or 0
    cases_today       = db.query(func.count(Case.id)).filter(
        Case.created_at >= today_start
    ).scalar() or 0
    cases_this_week   = db.query(func.count(Case.id)).filter(
        Case.created_at >= week_start
    ).scalar() or 0
    cases_this_month  = db.query(func.count(Case.id)).filter(
        Case.created_at >= month_start
    ).scalar() or 0
    sla_breached      = db.query(func.count(Case.id)).filter(
        Case.sla_breached == True,
        Case.status.notin_([CaseStatus.closed, CaseStatus.cancelled]),
    ).scalar() or 0
    sla_at_risk       = db.query(func.count(Case.id)).filter(
        Case.sla_due_at.isnot(None),
        Case.sla_due_at <= now + timedelta(hours=4),
        Case.status.notin_([CaseStatus.closed, CaseStatus.cancelled]),
    ).scalar() or 0

    # Cases by status
    cases_by_status = {}
    for s in CaseStatus:
        cases_by_status[s.value] = db.query(func.count(Case.id)).filter(Case.status == s).scalar() or 0

    # Cases by priority
    cases_by_priority = {}
    for p in CasePriority:
        cases_by_priority[p.value] = db.query(func.count(Case.id)).filter(
            Case.priority == p,
            Case.status.notin_([CaseStatus.closed, CaseStatus.cancelled]),
        ).scalar() or 0

    # ── Patients ──────────────────────────────────────────
    total_patients   = db.query(func.count(Patient.id)).scalar() or 0
    new_this_month   = db.query(func.count(Patient.id)).filter(
        Patient.created_at >= month_start
    ).scalar() or 0

    # ── Finance ──────────────────────────────────────────
    revenue_month    = db.query(func.sum(Payment.amount)).filter(
        Payment.received_at >= month_start
    ).scalar() or 0.0
    outstanding      = db.query(func.sum(Invoice.total_amount - Invoice.paid_amount)).filter(
        Invoice.status.in_([InvoiceStatus.sent, InvoiceStatus.partial, InvoiceStatus.overdue])
    ).scalar() or 0.0

    # ── WhatsApp ──────────────────────────────────────────
    open_conversations = db.query(func.count(Conversation.id)).filter(
        Conversation.status == ConversationStatus.open
    ).scalar() or 0
    messages_today   = db.query(func.count(Message.id)).filter(
        Message.created_at >= today_start
    ).scalar() or 0

    # ── Appointments ──────────────────────────────────────
    appts_today      = db.query(func.count(Appointment.id)).filter(
        Appointment.appointment_date >= today_start,
        Appointment.appointment_date < today_start + timedelta(days=1),
        Appointment.status.notin_([AppointmentStatus.cancelled]),
    ).scalar() or 0

    # ── Top countries ────────────────────────────────────
    top_countries = (
        db.query(Patient.country, func.count(Patient.id).label("count"))
        .filter(Patient.country.isnot(None))
        .group_by(Patient.country)
        .order_by(func.count(Patient.id).desc())
        .limit(5)
        .all()
    )

    # ── Cases by type ────────────────────────────────────
    cases_by_type = {}
    for t in CaseType:
        cases_by_type[t.value] = db.query(func.count(Case.id)).filter(Case.type == t).scalar() or 0

    # ── Monthly new cases (last 6 months) ────────────────
    monthly_cases = []
    for i in range(5, -1, -1):
        mo = (now.month - i - 1) % 12 + 1
        yr = now.year - ((i + (now.month - 1)) // 12)
        count = db.query(func.count(Case.id)).filter(
            extract("year", Case.created_at) == yr,
            extract("month", Case.created_at) == mo,
        ).scalar() or 0
        monthly_cases.append({
            "year": yr,
            "month": mo,
            "label": datetime(yr, mo, 1).strftime("%b %Y"),
            "count": count,
        })

    return {
        "cases": {
            "total": total_cases,
            "open": open_cases,
            "today": cases_today,
            "this_week": cases_this_week,
            "this_month": cases_this_month,
            "sla_breached": sla_breached,
            "sla_at_risk": sla_at_risk,
            "by_status": cases_by_status,
            "by_priority": cases_by_priority,
            "by_type": cases_by_type,
            "monthly": monthly_cases,
        },
        "patients": {
            "total": total_patients,
            "new_this_month": new_this_month,
            "top_countries": [{"country": c, "count": n} for c, n in top_countries],
        },
        "finance": {
            "revenue_this_month": round(revenue_month, 2),
            "outstanding": round(outstanding, 2),
        },
        "whatsapp": {
            "open_conversations": open_conversations,
            "messages_today": messages_today,
        },
        "appointments": {
            "today": appts_today,
        },
    }


@router.get("/cases")
def case_analytics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detailed case breakdown for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Resolution time (avg hours from opened_at to closed_at)
    resolved = db.query(Case).filter(
        Case.status == CaseStatus.closed,
        Case.closed_at.isnot(None),
        Case.opened_at.isnot(None),
        Case.created_at >= since,
    ).all()

    avg_resolution_hours = None
    if resolved:
        durations = [
            (c.closed_at - c.opened_at).total_seconds() / 3600
            for c in resolved
            if c.closed_at > c.opened_at
        ]
        avg_resolution_hours = round(sum(durations) / len(durations), 1) if durations else None

    # Cases by country of origin
    by_country = (
        db.query(Case.country_of_origin, func.count(Case.id).label("count"))
        .filter(Case.created_at >= since, Case.country_of_origin.isnot(None))
        .group_by(Case.country_of_origin)
        .order_by(func.count(Case.id).desc())
        .limit(10)
        .all()
    )

    # Cases by service type
    by_service = (
        db.query(Case.service_type, func.count(Case.id).label("count"))
        .filter(Case.created_at >= since, Case.service_type.isnot(None))
        .group_by(Case.service_type)
        .order_by(func.count(Case.id).desc())
        .limit(10)
        .all()
    )

    # Agent performance
    pass  # User already imported at module level
    agent_stats = (
        db.query(
            User.full_name,
            User.username,
            func.count(Case.id).label("assigned"),
        )
        .join(Case, Case.assigned_to == User.id, isouter=True)
        .filter(Case.created_at >= since)
        .group_by(User.id, User.full_name, User.username)
        .order_by(func.count(Case.id).desc())
        .limit(10)
        .all()
    )

    return {
        "period_days": days,
        "avg_resolution_hours": avg_resolution_hours,
        "by_country": [{"country": c, "count": n} for c, n in by_country],
        "by_service": [{"service": s, "count": n} for s, n in by_service],
        "agent_performance": [
            {"name": name or username, "username": username, "assigned": assigned}
            for name, username, assigned in agent_stats
        ],
    }


@router.get("/finance")
def finance_analytics(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Monthly revenue & billing breakdown."""
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(months - 1, -1, -1):
        mo = (now.month - i - 1) % 12 + 1
        yr = now.year - ((i + (now.month - 1)) // 12)
        billed = db.query(func.sum(Invoice.total_amount)).filter(
            extract("year", Invoice.created_at) == yr,
            extract("month", Invoice.created_at) == mo,
            Invoice.status != InvoiceStatus.void,
        ).scalar() or 0.0
        collected = db.query(func.sum(Payment.amount)).filter(
            extract("year", Payment.received_at) == yr,
            extract("month", Payment.received_at) == mo,
        ).scalar() or 0.0
        rows.append({
            "year": yr,
            "month": mo,
            "label": datetime(yr, mo, 1).strftime("%b %Y"),
            "billed": round(billed, 2),
            "collected": round(collected, 2),
        })

    return {"months": months, "data": rows}
