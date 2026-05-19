from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Cookie
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, UserRole
from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    session_token: Optional[str] = Cookie(default=None, alias="tmasi_session"),
    db: Session = Depends(get_db)
) -> User:
    resolved_token = token or session_token
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not resolved_token:
        raise credentials_exception
    try:
        payload = jwt.decode(resolved_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    session_token: Optional[str] = Cookie(default=None, alias="tmasi_session"),
    db: Session = Depends(get_db)
) -> Optional[User]:
    try:
        return get_current_user(token=token, session_token=session_token, db=db)
    except HTTPException:
        return None


# ── Role-based access control ─────────────────────────────────────
ADMIN_ROLES   = {UserRole.super_admin, UserRole.clinic_admin}
MANAGER_ROLES = {UserRole.super_admin, UserRole.clinic_admin}
FINANCE_ROLES = {UserRole.super_admin, UserRole.clinic_admin, UserRole.finance}
CASE_ROLES    = {UserRole.super_admin, UserRole.clinic_admin, UserRole.agent, UserRole.case_manager}
ALL_STAFF     = set(UserRole)


def require_roles(*roles: UserRole):
    """Dependency factory: returns current user if their role is in the allowed set."""
    allowed = set(roles)
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied for your role.",
            )
        return current_user
    return checker


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
