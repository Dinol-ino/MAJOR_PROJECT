import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.db.engine import get_sync_session
from app.db.models import DocumentMemory
from app.retrieval.tier2_user import Tier2UserRetrieval
from app.config import settings

logger = logging.getLogger(__name__)


class DocumentMemoryManager:
    """
    Layer 4 (L4) Document Memory:
    Manages document metadata in PostgreSQL and vector embeddings in ChromaDB.
    Enforces cascading deletion across both stores.
    """

    def __init__(self):
        try:
            self.retriever = Tier2UserRetrieval(persist_dir=settings.CHROMA_PERSIST_DIR)
        except Exception as exc:
            logger.debug(f"Tier2 retriever deferred in document memory: {exc}")
            self.retriever = None

    def record_document(
        self,
        doc_id: str,
        session_id: str,
        filename: str,
        file_size_bytes: Optional[int] = None,
        page_count: Optional[int] = None,
        chunk_count: Optional[int] = None,
        metadata_json: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Persists document metadata in PostgreSQL."""
        with get_sync_session() as session:
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
        """Retrieves list of documents uploaded for a specific session."""
        with get_sync_session() as session:
            docs = session.query(DocumentMemory).filter_by(
                session_id=session_id
            ).order_by(DocumentMemory.created_at.desc()).all()
            return [d.to_dict() for d in docs]

    def delete_document_cascade(self, doc_id: str, session_id: str) -> bool:
        """
        Cascading delete:
        1. Deletes metadata row from PostgreSQL.
        2. Deletes vector chunks from ChromaDB for this document.
        """
        # 1. Delete ChromaDB vector embeddings
        try:
            if hasattr(self.retriever, "collection") and self.retriever.collection:
                self.retriever.collection.delete(
                    where={"$and": [{"session_id": session_id}, {"doc_id": doc_id}]}
                )
        except Exception as e:
            logger.warning(f"ChromaDB chunk deletion for doc_id '{doc_id}' encountered: {e}")

        # 2. Delete PostgreSQL metadata row
        with get_sync_session() as session:
            doc = session.query(DocumentMemory).filter_by(doc_id=doc_id, session_id=session_id).first()
            if doc:
                session.delete(doc)
                return True
            return False


document_memory = DocumentMemoryManager()
