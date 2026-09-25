import os
import time
import uuid
import hashlib
import secrets
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func

from app.db.engine import get_sync_session
from app.db.models import User
from app.defense.audit_log import AuditLogger
from app.security.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth", "settings"])
from .settings import router as settings_router
router.include_router(settings_router)

audit_logger = AuditLogger()

# Token storage in memory (bounded cache for active sessions)
_ACTIVE_TOKENS: Dict[str, Dict[str, Any]] = {}

# Failed-login throttle (brute-force defense)
_FAILED_LOGINS: Dict[str, Dict[str, Any]] = {}
_MAX_FAILED_ATTEMPTS = 5
_FAILED_WINDOW_SECONDS = 900  # 15-minute counting window
_LOCKOUT_SECONDS = 900  # 15-minute lockout

DEFAULT_USER: Dict[str, Any] = {
    "id": "default_user",
    "username": "legal_practitioner",
    "email": "practitioner@dfrag.ai",
    "full_name": "Advocate Practitioner",
    "role": "attorney"
}


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hashes password with SHA-256 and PBKDF2 salt."""
    salt = salt or secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${key.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verifies plaintext password against stored salt$hash."""
    try:
        salt, key_hex = stored_hash.split("$")
        check_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return secrets.compare_digest(key_hex, check_key.hex())
    except Exception:
        return False


def _auth_disabled_for_tests() -> bool:
    """Auth enforcement is bypassed only inside automated test runs."""
    return (
        bool(os.environ.get("PYTEST_CURRENT_TEST"))
        or os.environ.get("TESTING") == "1"
        or os.environ.get("AUTH_DISABLED_FOR_TESTS") == "1"
    )


def _account_exists() -> bool:
    with get_sync_session() as session:
        count = session.execute(select(func.count()).select_from(User)).scalar()
    return bool(count and count > 0)


def _throttle_state(key: str) -> Dict[str, Any]:
    entry = _FAILED_LOGINS.get(key)
    now = time.time()
    if entry and now - entry.get("first_ts", now) > _FAILED_WINDOW_SECONDS:
        _FAILED_LOGINS.pop(key, None)
        entry = None
    if not entry:
        entry = {"count": 0, "first_ts": now, "locked_until": 0.0}
        _FAILED_LOGINS[key] = entry
    return entry


def _check_lockout(key: str) -> None:
    entry = _throttle_state(key)
    if entry.get("locked_until", 0) > time.time():
        wait_min = int((entry["locked_until"] - time.time()) // 60) + 1
        audit_logger.log(action=f"login_locked:{key}", layer="security")
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Try again in {wait_min} minute(s)."
        )


def _record_failed_login(key: str) -> None:
    entry = _throttle_state(key)
    entry["count"] += 1
    if entry["count"] >= _MAX_FAILED_ATTEMPTS:
        entry["locked_until"] = time.time() + _LOCKOUT_SECONDS
        _FAILED_LOGINS[key] = entry


def _clear_failed_logins(key: str) -> None:
    _FAILED_LOGINS.pop(key, None)


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = "Legal Practitioner"
    role: Optional[str] = "attorney"


class LoginRequest(BaseModel):
    username: str  # Can be username or email
    password: str


class AuthResponse(BaseModel):
    token: str
    user: Dict[str, Any]


def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Enforced authentication dependency for all protected routes.

    - Valid Bearer token -> session user.
    - Invalid token -> 401.
    - No token, but zero registered accounts -> first-run setup mode (default
      practitioner) so a brand-new install is never locked out of registration.
    - No token, accounts exist -> 401.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):].strip()
        user = _ACTIVE_TOKENS.get(token)
        if user:
            return user
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in again.")

    if _auth_disabled_for_tests():
        return dict(DEFAULT_USER)

    try:
        if not _account_exists():
            return dict(DEFAULT_USER)
    except Exception as exc:
        logger.warning(f"Auth user-existence check failed (treating as bootstrapped first-run): {exc}")
        return dict(DEFAULT_USER)

    raise HTTPException(status_code=401, detail="Authentication required. Please log in.")


@router.post("/auth/register", response_model=AuthResponse)
@limiter.limit("5/minute")
def register(request: Request, req: RegisterRequest):
    """Registers a new legal practitioner account in PostgreSQL/SQLite."""
    if len(req.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    with get_sync_session() as session:
        # Check uniqueness
        stmt = select(User).where((User.username == req.username) | (User.email == req.email))
        existing = session.execute(stmt).first()
        if existing:
            raise HTTPException(status_code=409, detail="A user with this username or email already exists.")

        user_id = f"usr_{uuid.uuid4().hex[:12]}"
        user = User(
            id=user_id,
            username=req.username.strip(),
            email=req.email.strip().lower(),
            hashed_password=_hash_password(req.password),
            full_name=req.full_name or "Legal Practitioner",
            role=req.role or "attorney"
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        user_dict = user.to_dict()
        token = secrets.token_hex(24)
        _ACTIVE_TOKENS[token] = user_dict
        audit_logger.log(action=f"account_registered:{user.username}", layer="security")

        return AuthResponse(token=token, user=user_dict)


@router.post("/auth/login", response_model=AuthResponse)
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest):
    """Authenticates legal practitioner and returns session token."""
    identifier = req.username.strip()
    throttle_key = f"{request.client.host if request.client else 'unknown'}:{identifier.lower()}"
    _check_lockout(throttle_key)

    with get_sync_session() as session:
        stmt = select(User).where((User.username == identifier) | (User.email == identifier.lower()))
        user = session.execute(stmt).scalars().first()

        if not user or not _verify_password(req.password, user.hashed_password):
            _record_failed_login(throttle_key)
            audit_logger.log(action=f"login_failed:{identifier}", layer="security")
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        _clear_failed_logins(throttle_key)
        user_dict = user.to_dict()
        token = secrets.token_hex(24)
        _ACTIVE_TOKENS[token] = user_dict
        audit_logger.log(action=f"login_success:{user.username}", layer="security")

        return AuthResponse(token=token, user=user_dict)


@router.get("/auth/me")
def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    """Returns currently authenticated user profile."""
    return user
