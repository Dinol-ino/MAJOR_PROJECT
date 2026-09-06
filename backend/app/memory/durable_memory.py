import os
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings
from app.db.models import Base, Conversation, Message, SemanticMemory, DocumentMemory
from app.db.engine import get_sync_engine, get_sync_session

logger = logging.getLogger(__name__)


class DurableMemoryManager:
    """
    Unified durable memory manager for conversations, messages, semantic facts/preferences,
    and document metadata.
    Uses SQLAlchemy ORM models against PostgreSQL (primary) or SQLite (fallback/testing).
    Enforces write-through persistence and strict user_id identity isolation.
    """
    def __init__(self, db_url_or_path: Optional[str] = None):
        self.custom_path = db_url_or_path
        if db_url_or_path:
            is_url = db_url_or_path.startswith("postgres://") or db_url_or_path.startswith("postgresql://") or db_url_or_path.startswith("sqlite://")
            url = db_url_or_path if is_url else f"sqlite:///{db_url_or_path}"
            connect_args = {"check_same_thread": False} if "sqlite" in url else {}
            self._engine = create_engine(url, connect_args=connect_args, echo=False)
            Base.metadata.create_all(bind=self._engine)
            self._session_factory = sessionmaker(bind=self._engine, autoflush=False, autocommit=False)
        else:
            self._engine = None
            self._session_factory = None
            try:
                engine = get_sync_engine()
                Base.metadata.create_all(bind=engine)
            except Exception as e:
                logger.warning(f"Could not verify database schema on startup: {e}")

    @contextmanager
    def _get_session(self):
        if self._session_factory:
            session: Session = self._session_factory()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        else:
            with get_sync_session() as session:
                yield session

    def create_conversation_if_not_exists(
        self, 
        conversation_id: str, 
        user_id: str = "default_user", 
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a conversation record if one does not already exist."""
        title = title or f"Task {conversation_id[:8]}"
        with self._get_session() as session:
            conv = session.query(Conversation).filter_by(conversation_id=conversation_id).first()
            if not conv:
                conv = Conversation(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    title=title,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(conv)
                session.flush()
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
        """
        Write-through persistence: inserts message into DB on every turn.
        """
        self.create_conversation_if_not_exists(conversation_id, user_id=user_id)
        message_id = str(uuid.uuid4())
        msg_obj = Message(
            message_id=message_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations,
            blocked_by=blocked_by,
            latency_ms=latency_ms,
            created_at=datetime.utcnow()
        )
        with self._get_session() as session:
            session.add(msg_obj)
            session.flush()
            return msg_obj.to_dict()

    def get_user_conversations(self, user_id: str = "default_user") -> List[Dict[str, Any]]:
        """
        Returns list of conversations bound to user_id for sidebar navigation.
        """
        with self._get_session() as session:
            convs = session.query(Conversation).filter_by(user_id=user_id).order_by(Conversation.created_at.desc()).all()
            return [c.to_dict() for c in convs]

    def get_conversation_messages(self, conversation_id: str, user_id: str = "default_user") -> List[Dict[str, Any]]:
        """
        Retrieves message history for a specific conversation, enforcing user_id identity isolation.
        """
        with self._get_session() as session:
            conv = session.query(Conversation).filter_by(conversation_id=conversation_id, user_id=user_id).first()
            if not conv:
                return []
            msgs = session.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.created_at.asc()).all()
            return [m.to_dict() for m in msgs]

    def delete_conversation(self, conversation_id: str, user_id: str = "default_user") -> bool:
        """Deletes conversation and cascade-deletes associated messages."""
        with self._get_session() as session:
            conv = session.query(Conversation).filter_by(conversation_id=conversation_id, user_id=user_id).first()
            if conv:
                session.delete(conv)
                return True
            return False

    # Semantic Memory Management (Facts & Preferences)
    def save_semantic_memory(self, user_id: str, category: str, key: str, value: str) -> Dict[str, Any]:
        with self._get_session() as session:
            mem = session.query(SemanticMemory).filter_by(user_id=user_id, category=category, key=key).first()
            if mem:
                mem.value = value
                mem.updated_at = datetime.utcnow()
            else:
                mem = SemanticMemory(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    category=category,
                    key=key,
                    value=value,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(mem)
            session.flush()
            return mem.to_dict()

    def get_semantic_memories(self, user_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            query = session.query(SemanticMemory).filter_by(user_id=user_id)
            if category:
                query = query.filter_by(category=category)
            mems = query.order_by(SemanticMemory.updated_at.desc()).all()
            return [m.to_dict() for m in mems]

    # Document Memory Metadata Management
    def save_document_memory(
        self,
        doc_id: str,
        session_id: str,
        filename: str,
        file_size_bytes: Optional[int] = None,
        page_count: Optional[int] = None,
        chunk_count: Optional[int] = None,
        metadata_json: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        with self._get_session() as session:
            doc = session.query(DocumentMemory).filter_by(doc_id=doc_id).first()
            if doc:
                doc.session_id = session_id
                doc.filename = filename
                doc.file_size_bytes = file_size_bytes
                doc.page_count = page_count
                doc.chunk_count = chunk_count
                doc.metadata_json = metadata_json
            else:
                doc = DocumentMemory(
                    doc_id=doc_id,
                    session_id=session_id,
                    filename=filename,
                    file_size_bytes=file_size_bytes,
                    page_count=page_count,
                    chunk_count=chunk_count,
                    metadata_json=metadata_json,
                    created_at=datetime.utcnow()
                )
                session.add(doc)
            session.flush()
            return doc.to_dict()

    def get_session_documents(self, session_id: str) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            docs = session.query(DocumentMemory).filter_by(session_id=session_id).order_by(DocumentMemory.created_at.desc()).all()
            return [d.to_dict() for d in docs]
