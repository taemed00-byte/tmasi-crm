"""Audit Log router — view and search the immutable action trail."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.auth import get_current_user
from app.models.user import User, UserRole
from app.models.audit import AuditLog

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _log_dict(l: AuditLog) -> dict:
    return {
        "id": l.id,
        "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        "user_id": l.user_id,
        "username": l.username,
        "user_role": l.user_role,
        "ip_address": l.ip_address,
        "action": l.action.value if l.action else None,
        "entity_type": l.entity_type,
        "entity_id": l.entity_id,
        "summary": l.summary,
        "session_id": l.session_id,
    }


@router.get("")
def list_audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    q: Optional[str] = None,
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if date_from:
        query = query.filter(AuditLog.timestamp >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(AuditLog.timestamp <= datetime.fromisoformat(date_to))
    if q:
        query = query.filter(or_(
            AuditLog.summary.ilike(f"%{q}%"),
            AuditLog.username.ilike(f"%{q}%"),
        ))
    total = query.count()
    logs = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_log_dict(l) for l in logs]}


@router.get("/entity/{entity_type}/{entity_id}")
def entity_audit_trail(
    entity_type: str, entity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logs = db.query(AuditLog).filter(
        AuditLog.entity_type == entity_type,
        AuditLog.entity_id == entity_id,
    ).order_by(AuditLog.timestamp.desc()).all()
    return [_log_dict(l) for l in logs]
