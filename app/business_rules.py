"""Business Rules Engine — SLA breach checker and automated alerts."""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.case import Case, CaseStatus, CasePriority, CaseNote, NoteType, OPEN_STATUSES

logger = logging.getLogger(__name__)


def check_sla_breaches():
    """Mark cases where sla_due_at has passed. Call periodically."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        breached = db.query(Case).filter(
            Case.status.in_(OPEN_STATUSES),
            Case.sla_due_at != None,
            Case.sla_due_at < now,
            Case.sla_breached == False,
        ).all()
        for case in breached:
            case.sla_breached = True
            note = CaseNote(
                case_id=case.id,
                body=f"SLA BREACHED — due {case.sla_due_at.strftime('%Y-%m-%d %H:%M')} UTC. Case escalated automatically.",
                note_type=NoteType.escalation,
                is_internal=True,
            )
            db.add(note)
            # Bump priority
            if case.priority == CasePriority.normal:
                case.priority = CasePriority.high
            elif case.priority == CasePriority.high:
                case.priority = CasePriority.urgent
            logger.warning(f"SLA breached for case {case.case_number}")
        if breached:
            db.commit()
            logger.info(f"SLA check: {len(breached)} cases marked breached")
    except Exception as e:
        logger.error(f"SLA check error: {e}")
        db.rollback()
    finally:
        db.close()


def check_inactive_cases():
    """Auto-escalate cases inactive for 7+ days."""
    db = SessionLocal()
    try:
        threshold = datetime.now(timezone.utc) - timedelta(days=7)
        stale = db.query(Case).filter(
            Case.status.in_(OPEN_STATUSES),
            Case.updated_at < threshold,
        ).all()
        for case in stale:
            note = CaseNote(
                case_id=case.id,
                body="Auto-escalation: Case has had no activity for 7+ days. Manager review required.",
                note_type=NoteType.escalation,
                is_internal=True,
            )
            db.add(note)
            if case.priority == CasePriority.low:
                case.priority = CasePriority.normal
            elif case.priority == CasePriority.normal:
                case.priority = CasePriority.high
        if stale:
            db.commit()
            logger.info(f"Inactivity check: {len(stale)} cases escalated")
    except Exception as e:
        logger.error(f"Inactivity check error: {e}")
        db.rollback()
    finally:
        db.close()


def is_provider_blacklisted(db: Session, provider_id: str) -> bool:
    """Hard block: returns True if provider is blacklisted."""
    from app.models.clinic import Clinic
    if not provider_id:
        return False
    p = db.query(Clinic).filter(Clinic.id == provider_id).first()
    return p is not None and getattr(p, "category", "standard") == "blacklisted"


def validate_case_rules(db: Session, case: Case) -> list:
    """Return list of rule violations (strings) for a case before saving."""
    violations = []
    # Blacklisted provider check
    if case.clinic_id and is_provider_blacklisted(db, case.clinic_id):
        violations.append("Provider is BLACKLISTED and cannot be assigned to new cases.")
    return violations
