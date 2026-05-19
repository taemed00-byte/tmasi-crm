"""Audit helper — call audit_event() from any router to record an action."""
import json
from datetime import datetime, timezone
from fastapi import Request
from sqlalchemy.orm import Session
from app.models.audit import AuditLog, AuditAction
from app.models.user import User


def audit_event(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str = None,
    summary: str = None,
    before: dict = None,
    after: dict = None,
    user: User = None,
    request: Request = None,
):
    """Write a single audit record. Silently swallows errors so it never breaks callers."""
    try:
        ip = None
        ua = None
        session_id = None
        if request:
            ip = request.client.host if request.client else None
            ua = request.headers.get("user-agent", "")[:300]
            session_id = request.cookies.get("tmasi_session", "")[:100]

        log = AuditLog(
            action=AuditAction(action) if action in AuditAction._value2member_map_ else AuditAction.update,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            summary=summary,
            before_state=json.dumps(before, default=str) if before else None,
            after_state=json.dumps(after, default=str) if after else None,
            user_id=user.id if user else None,
            username=user.username if user else None,
            user_role=user.role.value if user and user.role else None,
            ip_address=ip,
            user_agent=ua,
            session_id=session_id,
        )
        db.add(log)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
