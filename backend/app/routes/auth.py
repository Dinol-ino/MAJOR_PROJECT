"""
Authentication & session management.

Design (fail-closed):
- Every protected route requires a valid signed session token. There is no
  token-less "first-run" user: a fresh install exposes only /auth/status,
  /auth/register and /auth/login until an account exists.
- Tokens are HS-signed JWTs carrying a unique `jti`; logout revokes the jti.
- Database errors while authenticating yield 503, never an anonymous identity.
- The signing secret comes from JWT_SECRET_KEY. If it is missing, an ephemeral
  per-process secret is generated (sessions end on restart) and a warning is
  logged. There is no hardcoded fallback secret.
"""
import os
import sys
import time
import uuid
import hashlib
import secrets
import logging
import threading
from collections import OrderedDict
from typing import Optional, Dict, Any

import jwt
from fastapi import APIRouter, HTTPException, Depends, Header, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, func

from app.config import settings
from app.db.engine import get_sync_session, DatabaseUnavailableError
from app.db.models import User
from app.defense.audit_log import AuditLogger
from app.security.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])

audit_logger = AuditLogger()

_auth_cfg = settings.auth
if _auth_cfg.jwt_secret:
    AUTH_SECRET = _auth_cfg.jwt_secret
else:
    AUTH_SECRET = secrets.token_urlsafe(48)
    logger.warning(
        "JWT_SECRET_KEY is not set: using an ephemeral per-process signing key. "
        "All sessions will be invalidated when the backend restarts. Set JWT_SECRET_KEY in .env."
    )
AUTH_ALGORITHM = _auth_cfg.jwt_algorithm
AUTH_TOKEN_EXPIRE_SECONDS = _auth_cfg.session_ttl_seconds

# Streaming endpoints (EventSource / fetch streams through proxies) may carry the
# session token as ?token=. It is accepted ONLY for these GET paths so tokens do
# not end up in access logs for ordinary API calls.
_QUERY_TOKEN_PATH_SUFFIXES = ("/stream",)

# Identity used only when the process is running under pytest.
_TEST_USER: Dict[str, Any] = {
    "id": "default_user",
    "username": "legal_practitioner",
    "email": "practitioner@dfrag.invalid",
    "full_name": "Test Practitioner",
    "role": "attorney",
}


class _BoundedTokenCache:
    """Thread-safe LRU cache of verified tokens -> (user, exp). Entries honour token expiry."""

    def __init__(self, max_entries: int):
        self._max = max(16, max_entries)
        self._data: "OrderedDict[str, tuple]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, token: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._data.get(token)
            if not item:
                return None
            user, exp = item
            if exp <= time.time():
                self._data.pop(token, None)
                return None
            self._data.move_to_end(token)
            return dict(user)

    def put(self, token: str, user: Dict[str, Any], exp: float) -> None:
        with self._lock:
            self._data[token] = (dict(user), exp)
            self._data.move_to_end(token)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def discard(self, token: str) -> None:
        with self._lock:
            self._data.pop(token, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class _RevocationList:
    """Revoked token ids (jti) kept until the token would have expired anyway. Process-local."""

    def __init__(self, max_entries: int):
        self._max = max(64, max_entries)
        self._data: "OrderedDict[str, float]" = OrderedDict()
        self._lock = threading.Lock()

    def revoke(self, jti: str, exp: float) -> None:
        with self._lock:
            self._data[jti] = exp
            now = time.time()
            for key in [k for k, v in self._data.items() if v <= now]:
                self._data.pop(key, None)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def is_revoked(self, jti: Optional[str]) -> bool:
        if not jti:
            return False
        with self._lock:
            return jti in self._data


_TOKEN_CACHE = _BoundedTokenCache(_auth_cfg.token_cache_max_entries)
_REVOKED = _RevocationList(_auth_cfg.token_cache_max_entries)

# Failed-login throttle (brute-force defense). Bounded by key count.
_FAILED_LOGINS: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_FAILED_LOCK = threading.Lock()
_MAX_THROTTLE_KEYS = 10_000
_MAX_FAILED_ATTEMPTS = _auth_cfg.max_failed_attempts
_FAILED_WINDOW_SECONDS = _auth_cfg.lockout_seconds
_LOCKOUT_SECONDS = _auth_cfg.lockout_seconds


def _generate_token(user_id: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + AUTH_TOKEN_EXPIRE_SECONDS,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, AUTH_SECRET, algorithm=AUTH_ALGORITHM)


def _decode_payload(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(
            token,
            AUTH_SECRET,
            algorithms=[AUTH_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.PyJWTError:
        return None
    if _REVOKED.is_revoked(payload.get("jti")):
        return None
    return payload


def _decode_token(token: str) -> Optional[str]:
    payload = _decode_payload(token)
    return payload.get("sub") if payload else None


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    """PBKDF2-HMAC-SHA256 with a per-user random salt."""
    salt = salt or secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${key.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, key_hex = stored_hash.split("$")
        check_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return secrets.compare_digest(key_hex, check_key.hex())
    except Exception:
        return False


def _auth_disabled_for_tests() -> bool:
    """Only an in-process pytest run may use the fixed test identity (env vars cannot enable it)."""
    return "pytest" in sys.modules and bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _account_exists() -> bool:
    with get_sync_session() as session:
        count = session.execute(select(func.count()).select_from(User)).scalar()
    return bool(count and count > 0)


def _throttle_state(key: str) -> Dict[str, Any]:
    now = time.time()
    entry = _FAILED_LOGINS.get(key)
    if entry and now - entry.get("first_ts", now) > _FAILED_WINDOW_SECONDS and entry.get("locked_until", 0) <= now:
        _FAILED_LOGINS.pop(key, None)
        entry = None
    if not entry:
        entry = {"count": 0, "first_ts": now, "locked_until": 0.0}
        _FAILED_LOGINS[key] = entry
        while len(_FAILED_LOGINS) > _MAX_THROTTLE_KEYS:
            _FAILED_LOGINS.popitem(last=False)
    return entry


def _check_lockout(key: str) -> None:
    with _FAILED_LOCK:
        entry = _throttle_state(key)
        locked_until = entry.get("locked_until", 0)
    if locked_until > time.time():
        wait_min = int((locked_until - time.time()) // 60) + 1
        audit_logger.log(action="login_locked", layer="security")
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Try again in {wait_min} minute(s).",
        )


def _record_failed_login(key: str) -> None:
    with _FAILED_LOCK:
        entry = _throttle_state(key)
        entry["count"] += 1
        if entry["count"] >= _MAX_FAILED_ATTEMPTS:
            entry["locked_until"] = time.time() + _LOCKOUT_SECONDS


def _clear_failed_logins(key: str) -> None:
    with _FAILED_LOCK:
        _FAILED_LOGINS.pop(key, None)


def _identifier_fingerprint(identifier: str) -> str:
    """Audit-safe identifier (never log raw usernames/emails)."""
    return hashlib.sha256(identifier.strip().lower().encode("utf-8")).hexdigest()[:12]


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = "Legal Practitioner"
    # Accepted for backwards compatibility but ignored: roles are never self-assigned.
    role: Optional[str] = None


class LoginRequest(BaseModel):
    username: str  # username or email
    password: str


class AuthResponse(BaseModel):
    token: str
    user: Dict[str, Any]


def _extract_token(request: Optional[Request], authorization: Optional[str], token: Optional[str]) -> Optional[str]:
    if authorization and authorization.startswith("Bearer "):
        bearer = authorization[len("Bearer "):].strip()
        if bearer:
            return bearer
    if token and request is not None:
        path = request.url.path.rstrip("/")
        if request.method == "GET" and path.endswith(_QUERY_TOKEN_PATH_SUFFIXES):
            return token.strip() or None
    return None


def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None, include_in_schema=False),
) -> Dict[str, Any]:
    """
    Enforced authentication dependency for all protected routes (fail-closed).
    """
    candidate = _extract_token(request, authorization, token)
    if candidate:
        cached = _TOKEN_CACHE.get(candidate)
        if cached:
            return cached
        payload = _decode_payload(candidate)
        if payload:
            try:
                with get_sync_session() as session:
                    db_user = session.execute(select(User).where(User.id == payload["sub"])).scalar_one_or_none()
                    if db_user:
                        user_dict = db_user.to_dict()
                        _TOKEN_CACHE.put(candidate, user_dict, float(payload["exp"]))
                        return user_dict
            except DatabaseUnavailableError:
                raise HTTPException(status_code=503, detail="Authentication service unavailable: database is not reachable.")
            except HTTPException:
                raise
            except Exception as exc:
                logger.error("Session restore failed: %s", type(exc).__name__)
                raise HTTPException(status_code=503, detail="Authentication service unavailable.")
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in again.")

    if _auth_disabled_for_tests():
        return dict(_TEST_USER)

    raise HTTPException(status_code=401, detail="Authentication required. Please log in.")


@router.get("/auth/status")
@limiter.limit("60/minute")
def auth_status(request: Request):
    """Public bootstrap probe: tells the UI whether to show sign-in or first-account registration."""
    try:
        accounts_exist = _account_exists()
    except DatabaseUnavailableError:
        raise HTTPException(status_code=503, detail="Database is not reachable. Check DATABASE_URL and that PostgreSQL is running.")
    return {
        "accounts_exist": accounts_exist,
        "registration_open": _auth_cfg.registration_open or not accounts_exist,
        "password_min_length": _auth_cfg.password_min_length,
    }


@router.post("/auth/register", response_model=AuthResponse)
@limiter.limit("5/minute")
def register(request: Request, req: RegisterRequest):
    """Registers a practitioner account. The first account is always allowed."""
    username = req.username.strip()
    email = req.email.strip().lower()
    if len(username) < 3 or len(username) > 64:
        raise HTTPException(status_code=400, detail="Username must be between 3 and 64 characters.")
    if "@" not in email or len(email) > 128:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    if len(req.password) < _auth_cfg.password_min_length:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {_auth_cfg.password_min_length} characters.",
        )
    if len(req.password) > 256:
        raise HTTPException(status_code=400, detail="Password is too long.")

    try:
        with get_sync_session() as session:
            has_accounts = bool(session.execute(select(func.count()).select_from(User)).scalar())
            if has_accounts and not _auth_cfg.registration_open:
                raise HTTPException(status_code=403, detail="Registration is closed on this workspace.")

            stmt = select(User).where((User.username == username) | (User.email == email))
            if session.execute(stmt).first():
                raise HTTPException(status_code=409, detail="A user with this username or email already exists.")

            user = User(
                id=f"usr_{uuid.uuid4().hex[:12]}",
                username=username,
                email=email,
                hashed_password=_hash_password(req.password),
                full_name=(req.full_name or "Legal Practitioner")[:128],
                role="attorney",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            user_dict = user.to_dict()
    except DatabaseUnavailableError:
        raise HTTPException(status_code=503, detail="Database is not reachable.")

    token = _generate_token(user_dict["id"])
    _TOKEN_CACHE.put(token, user_dict, time.time() + AUTH_TOKEN_EXPIRE_SECONDS)
    audit_logger.log(action=f"account_registered:{_identifier_fingerprint(username)}", layer="security")
    return AuthResponse(token=token, user=user_dict)


@router.post("/auth/login", response_model=AuthResponse)
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest):
    """Authenticates a practitioner and returns a session token."""
    identifier = req.username.strip()
    client_host = request.client.host if request.client else "unknown"
    throttle_key = f"{client_host}:{identifier.lower()}"
    _check_lockout(throttle_key)

    try:
        with get_sync_session() as session:
            stmt = select(User).where((User.username == identifier) | (User.email == identifier.lower()))
            user = session.execute(stmt).scalars().first()
            valid = bool(user) and _verify_password(req.password, user.hashed_password)
            user_dict = user.to_dict() if (user and valid) else None
    except DatabaseUnavailableError:
        raise HTTPException(status_code=503, detail="Database is not reachable.")

    if not user_dict:
        _record_failed_login(throttle_key)
        audit_logger.log(action=f"login_failed:{_identifier_fingerprint(identifier)}", layer="security")
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    _clear_failed_logins(throttle_key)
    token = _generate_token(user_dict["id"])
    _TOKEN_CACHE.put(token, user_dict, time.time() + AUTH_TOKEN_EXPIRE_SECONDS)
    audit_logger.log(action=f"login_success:{_identifier_fingerprint(identifier)}", layer="security")
    return AuthResponse(token=token, user=user_dict)


@router.post("/auth/logout")
def logout(request: Request, authorization: Optional[str] = Header(None)):
    """Revokes the presented session token (idempotent)."""
    candidate = _extract_token(request, authorization, None)
    if candidate:
        _TOKEN_CACHE.discard(candidate)
        try:
            payload = jwt.decode(candidate, AUTH_SECRET, algorithms=[AUTH_ALGORITHM])
            if payload.get("jti"):
                _REVOKED.revoke(payload["jti"], float(payload.get("exp", time.time())))
        except jwt.PyJWTError:
            pass
    return {"status": "logged_out"}


@router.get("/auth/me")
def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    """Returns the authenticated user profile."""
    return user
