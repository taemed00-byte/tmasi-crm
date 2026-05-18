from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user, get_password_hash
from app.models.user import User, UserRole
from pydantic import BaseModel

router = APIRouter(prefix="/api/users", tags=["users"])


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = "agent"


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


def user_dict(u: User) -> dict:
    return {
        "id": u.id, "username": u.username, "full_name": u.full_name,
        "email": u.email, "role": u.role, "is_active": u.is_active,
        "created_at": u.created_at.isoformat(),
    }


@router.get("")
def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in [UserRole.super_admin, UserRole.clinic_admin]:
        raise HTTPException(403, "Insufficient permissions")
    return [user_dict(u) for u in db.query(User).order_by(User.username).all()]


@router.post("")
def create_user(req: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in [UserRole.super_admin, UserRole.clinic_admin]:
        raise HTTPException(403, "Insufficient permissions")
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(400, "Username already exists")
    u = User(
        username=req.username,
        full_name=req.full_name,
        email=req.email,
        hashed_password=get_password_hash(req.password),
        role=req.role or "agent",
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return user_dict(u)


@router.patch("/{user_id}")
def update_user(user_id: str, req: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in [UserRole.super_admin, UserRole.clinic_admin] and current_user.id != user_id:
        raise HTTPException(403, "Insufficient permissions")
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(404, "User not found")
    if req.full_name is not None:
        u.full_name = req.full_name
    if req.email is not None:
        u.email = req.email
    if req.role is not None and current_user.role == UserRole.super_admin:
        u.role = req.role
    if req.is_active is not None and current_user.role in [UserRole.super_admin, UserRole.clinic_admin]:
        u.is_active = req.is_active
    if req.password:
        u.hashed_password = get_password_hash(req.password)
    db.commit()
    db.refresh(u)
    return user_dict(u)


@router.delete("/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.super_admin:
        raise HTTPException(403, "Insufficient permissions")
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(404, "Not found")
    u.is_active = False
    db.commit()
    return {"ok": True}
