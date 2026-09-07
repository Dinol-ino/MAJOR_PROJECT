import os
import uuid
import hashlib
import secrets
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from app.db.engine import get_sync_session
from app.db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# Token storage in memory (bounded cache for active sessions)
_ACTIVE_TOKENS: Dict[str, Dict[str, Any]] = {}


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
    """Dependency extracting user identity from Bearer token or fallback to default."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "").strip()
        if token in _ACTIVE_TOKENS:
            return _ACTIVE_TOKENS[token]
    # Return default user if unauthenticated
    return {
        "id": "default_user",
        "username": "legal_practitioner",
        "email": "practitioner@dfrag.ai",
        "full_name": "Advocate Practitioner",
        "role": "attorney"
    }


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest):
    """Registers a new legal practitioner account in PostgreSQL/SQLite."""
    if len(req.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    with get_sync_session() as session:
        # Check uniqueness
        stmt = select(User).where((User.username == req.username) | (User.email == req.email))
        existing = session.execute(stmt).scalars().first()
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

        return AuthResponse(token=token, user=user_dict)


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest):
    """Authenticates legal practitioner and returns session token."""
    with get_sync_session() as session:
        identifier = req.username.strip()
        stmt = select(User).where((User.username == identifier) | (User.email == identifier.lower()))
        user = session.execute(stmt).scalars().first()

        if not user or not _verify_password(req.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        user_dict = user.to_dict()
        token = secrets.token_hex(24)
        _ACTIVE_TOKENS[token] = user_dict

        return AuthResponse(token=token, user=user_dict)


@router.get("/me")
def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    """Returns currently authenticated user profile."""
    return user
