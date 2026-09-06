import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import select, delete
from app.db.engine import get_sync_session
from app.db.models import Conversation, Message
from app.memory.policies import policies
from app.config import settings

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Layer 2 (L2) Conversation Memory:
    Durable, write-through conversation and message history.
    Stored in PostgreSQL tables `conversations` and `messages`.
    Enforces strict user identity isolation.
    """

    def __init__(self):
        self._active_cache: Dict[str, List[Dict[str, Any]]] = {}

    def get_or_create_conversation(
        self,
        conversation_id: str,
        user_id: str = "default_user",
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        with get_sync_session() as session:
            conv = session.query(Conversation).filter_by(conversation_id=conversation_id).first()
            if not conv:
                conv = Conversation(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    title=title or f"Chat {conversation_id[:8]}",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(conv)
                session.flush()
            elif not policies.validate_user_access(conv.user_id, user_id):
                raise PermissionError(f"User '{user_id}' is not authorized to access conversation '{conversation_id}'.")
            return conv.to_dict()

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        citations: Optional[List[Dict[str, Any]]] = None,
        user_id: str = "default_user",
        blocked_by: Optional[str] = None,
        latency_ms: Optional[float] = None
    ) -> Dict[str, Any]:
        """Appends a new turn message with write-through persistence to PostgreSQL."""
        self.get_or_create_conversation(conversation_id, user_id=user_id)
        msg_id = str(uuid.uuid4())
        msg = Message(
            message_id=msg_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations,
            blocked_by=blocked_by,
            latency_ms=latency_ms,
            created_at=datetime.utcnow(),
        )
        with get_sync_session() as session:
            session.add(msg)
            # Update conversation timestamp
            conv = session.query(Conversation).filter_by(conversation_id=conversation_id).first()
            if conv:
                conv.updated_at = datetime.utcnow()
            session.flush()
            result = msg.to_dict()

        # Invalidate/update local cache
        if conversation_id in self._active_cache:
            self._active_cache[conversation_id].append(result)
        return result

    def get_messages(
        self,
        conversation_id: str,
        user_id: str = "default_user",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieves messages for a conversation, enforcing user isolation."""
        with get_sync_session() as session:
            conv = session.query(Conversation).filter_by(conversation_id=conversation_id).first()
            if not conv:
                return []
            if not policies.validate_user_access(conv.user_id, user_id):
                raise PermissionError(f"User '{user_id}' is not authorized to view messages for conversation '{conversation_id}'.")

            msgs = session.query(Message).filter_by(
                conversation_id=conversation_id
            ).order_by(Message.created_at.asc()).limit(limit).all()
            return [m.to_dict() for m in msgs]

    def list_conversations(self, user_id: str = "default_user") -> List[Dict[str, Any]]:
        """Lists all conversations for the authenticated user."""
        with get_sync_session() as session:
            convs = session.query(Conversation).filter_by(
                user_id=user_id
            ).order_by(Conversation.updated_at.desc()).all()
            return [c.to_dict() for c in convs]

    def delete_conversation(self, conversation_id: str, user_id: str = "default_user") -> bool:
        """Deletes conversation and cascade-deletes its messages."""
        with get_sync_session() as session:
            conv = session.query(Conversation).filter_by(conversation_id=conversation_id).first()
            if not conv:
                return False
            if not policies.validate_user_access(conv.user_id, user_id):
                raise PermissionError(f"User '{user_id}' is not authorized to delete conversation '{conversation_id}'.")

            session.delete(conv)
            if conversation_id in self._active_cache:
                del self._active_cache[conversation_id]
            return True


conversation_memory = ConversationMemory()
