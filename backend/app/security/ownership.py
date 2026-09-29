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


def owns(resource_owner: Optional[str], user: Dict[str, Any], write: bool = False) -> bool:
    """True when the user may act on the resource.

    Admins may READ across users so they can administer the workspace, but not write:
    a practitioner's matter files are privileged, and silently letting an admin edit or
    delete another practitioner's vault would break the isolation this product sells.
    Pass write=True on any mutating path to require actual ownership.
    """
    owned = bool(resource_owner) and resource_owner == current_user_id(user)
    if owned:
        return True
    return is_admin(user) and not write


def require_vault(session, vault_id: str, user: Dict[str, Any], include_deleted: bool = False,
                  write: bool = False):
    from app.db.models import ProjectVault

    query = session.query(ProjectVault).filter(ProjectVault.id == vault_id)
    if not include_deleted:
        query = query.filter(ProjectVault.deleted_at.is_(None))
    vault = query.first()
    if not vault or not owns(vault.user_id, user, write=write):
        raise HTTPException(status_code=404, detail="Project vault not found.")
    return vault


def require_conversation(session, conversation_id: str, user: Dict[str, Any], write: bool = False):
    from app.db.models import Conversation

    conv = session.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    if not conv or not owns(conv.user_id, user, write=write):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conv


def conversation_accessible(session, conversation_id: str, user: Dict[str, Any]) -> bool:
    """True if the conversation does not exist yet (caller may create it) or is owned by the user."""
    from app.db.models import Conversation

    conv = session.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    return conv is None or owns(conv.user_id, user)
