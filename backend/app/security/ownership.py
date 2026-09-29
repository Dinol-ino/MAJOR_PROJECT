"""
Tenant/data isolation helpers.

All ownership decisions derive from the authenticated identity returned by
`get_current_user`. Client-supplied user identifiers are never trusted.
Resources owned by another user are reported as 404 so their existence is not
disclosed.
"""
from typing import Any, Dict, Optional

from fastapi import HTTPException


def current_user_id(user: Dict[str, Any]) -> str:
    uid = (user or {}).get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")
    return str(uid)


def is_admin(user: Dict[str, Any]) -> bool:
    return (user or {}).get("role") == "admin"


def owns(resource_owner: Optional[str], user: Dict[str, Any]) -> bool:
    """True when the authenticated user owns the resource (admins may read across users)."""
    if is_admin(user):
        return True
    return bool(resource_owner) and resource_owner == current_user_id(user)


def require_vault(session, vault_id: str, user: Dict[str, Any], include_deleted: bool = False):
    from app.db.models import ProjectVault

    query = session.query(ProjectVault).filter(ProjectVault.id == vault_id)
    if not include_deleted:
        query = query.filter(ProjectVault.deleted_at.is_(None))
    vault = query.first()
    if not vault or not owns(vault.user_id, user):
        raise HTTPException(status_code=404, detail="Project vault not found.")
    return vault


def require_conversation(session, conversation_id: str, user: Dict[str, Any]):
    from app.db.models import Conversation

    conv = session.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    if not conv or not owns(conv.user_id, user):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conv


def conversation_accessible(session, conversation_id: str, user: Dict[str, Any]) -> bool:
    """True if the conversation does not exist yet (caller may create it) or is owned by the user."""
    from app.db.models import Conversation

    conv = session.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    return conv is None or owns(conv.user_id, user)
