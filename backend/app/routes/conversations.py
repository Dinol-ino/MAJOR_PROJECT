import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.engine import get_sync_session
from app.db.models import Conversation, Message, ProjectVault
from app.defense.audit_log import AuditLogger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])
audit_logger = AuditLogger()


class CreateConversationRequest(BaseModel):
    project_vault_id: Optional[str] = Field(None, description="Optional Vault ID to bind this chat to")
    title: Optional[str] = Field("New Legal Chat", max_length=255)
    user_id: Optional[str] = Field("default_user")


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="New title for the chat session")
    project_vault_id: Optional[str] = Field(None, description="Move conversation to a different vault")


@router.post("", status_code=201)
def create_conversation(req: CreateConversationRequest):
    """Creates a new durable conversation, optionally associated with a project vault."""
    with get_sync_session() as session:
        if req.project_vault_id:
            vault = session.query(ProjectVault).filter(ProjectVault.id == req.project_vault_id).first()
            if not vault:
                raise HTTPException(status_code=404, detail="Specified project vault does not exist.")

        conv = Conversation(
            conversation_id=str(uuid.uuid4()),
            project_vault_id=req.project_vault_id,
            user_id=req.user_id or "default_user",
            title=req.title or "New Legal Chat",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(conv)
        session.flush()
        res = conv.to_dict()

    audit_logger.log(action=f"conversation_created:{res['conversation_id']}", layer="persistence")
    return res


@router.get("")
def list_conversations(
    vault_id: Optional[str] = Query(None, description="Filter chats by Project Vault ID"),
    user_id: str = Query("default_user", description="Filter by user ID"),
):
    """Lists conversations, ordered by updated_at desc."""
    with get_sync_session() as session:
        query = session.query(Conversation).filter(Conversation.user_id == user_id)
        if vault_id is not None:
            if vault_id == "unfiled":
                query = query.filter(Conversation.project_vault_id.is_(None))
            else:
                query = query.filter(Conversation.project_vault_id == vault_id)

        convs = query.order_by(Conversation.updated_at.desc()).all()
        data = []
        for c in convs:
            d = c.to_dict()
            d["message_count"] = len(c.messages)
            data.append(d)

    return {"conversations": data, "count": len(data)}


@router.get("/{conversation_id}")
def get_conversation_history(conversation_id: str):
    """Retrieves conversation metadata and full ordered message history for L2 rehydration."""
    with get_sync_session() as session:
        conv = session.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        messages = [m.to_dict() for m in conv.messages]
        res = conv.to_dict()

    res["messages"] = messages
    return res


@router.patch("/{conversation_id}")
def update_conversation(conversation_id: str, req: UpdateConversationRequest):
    """Renames a conversation or reassigns it to another vault (Spec 01 §3.3)."""
    with get_sync_session() as session:
        conv = session.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        if req.title is not None:
            conv.title = req.title.strip()
        if req.project_vault_id is not None:
            if req.project_vault_id != "":
                vault = session.query(ProjectVault).filter(ProjectVault.id == req.project_vault_id).first()
                if not vault:
                    raise HTTPException(status_code=404, detail="Target project vault does not exist.")
                conv.project_vault_id = req.project_vault_id
            else:
                conv.project_vault_id = None

        conv.updated_at = datetime.utcnow()
        session.flush()
        res = conv.to_dict()

    audit_logger.log(action=f"conversation_renamed:{conversation_id}", layer="persistence")
    return res


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str):
    """Deletes a conversation and cascades deletion to all messages."""
    with get_sync_session() as session:
        conv = session.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        session.delete(conv)

    audit_logger.log(action=f"conversation_deleted:{conversation_id}", layer="persistence")
    return {"status": "deleted", "conversation_id": conversation_id}
