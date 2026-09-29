from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from app.routes.auth import get_current_user
from app.security.ownership import current_user_id, require_conversation
from app.db.engine import get_sync_session

from app.memory import (
    semantic_memory,
    research_memory,
    document_memory,
    conversation_memory,
    audit_memory,
)

router = APIRouter(prefix="/memory", tags=["Layered Memory"])


class SemanticMemoryProposal(BaseModel):
    category: str = Field(..., description="Category: preference | fact | entity | jurisdiction | practice_area")
    key: str = Field(..., min_length=2, max_length=128)
    value: str = Field(..., min_length=1, max_length=2000)
    consent_given: bool = Field(True, description="Explicit user confirmation for long-term storage")


@router.get("/semantic")
def list_semantic_memories(
    category: Optional[str] = Query(None, description="Optional category filter"),
    current_user: Dict = Depends(get_current_user),
):
    """
    Transparency requirement: lists the authenticated user's explicit semantic memory entries.
    """
    user_id = current_user_id(current_user)
    memories = semantic_memory.get_user_memories(user_id=user_id, category=category)
    return {"user_id": user_id, "count": len(memories), "memories": memories}


@router.post("/semantic")
def propose_semantic_memory(
    proposal: SemanticMemoryProposal,
    current_user: Dict = Depends(get_current_user),
):
    """
    Proposes a semantic fact/preference. Runs through the strict L3 Validation Gate.
    """
    user_id = current_user_id(current_user)
    try:
        saved = semantic_memory.propose_and_save(
            user_id=user_id,
            category=proposal.category,
            key=proposal.key,
            value=proposal.value,
            consent_given=proposal.consent_given
        )
        return {"status": "saved", "entry": saved}
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal memory error.")


@router.delete("/semantic/{memory_id}")
def delete_semantic_memory(
    memory_id: str,
    current_user: Dict = Depends(get_current_user),
):
    """
    Explicit user-initiated deletion of an L3 semantic memory entry.
    """
    user_id = current_user_id(current_user)
    try:
        success = semantic_memory.delete_memory(memory_id=memory_id, user_id=user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        return {"status": "deleted", "memory_id": memory_id}
    except PermissionError:
        raise HTTPException(status_code=404, detail="Memory entry not found")


@router.get("/research/{session_id}")
def get_research_session(session_id: str, current_user: Dict = Depends(get_current_user)):
    """
    Retrieves an L5 research session's findings, provenance sources, and citations.
    """
    with get_sync_session() as db:
        require_conversation(db, session_id, current_user)
    session_data = research_memory.get_research_session(session_id=session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Research session not found")
    return session_data


@router.delete("/documents/{doc_id}")
def delete_document_cascade(
    doc_id: str,
    session_id: str = Query(..., description="Session identifier for the document"),
    current_user: Dict = Depends(get_current_user),
):
    """
    L4 Deletion Cascade: removes document metadata from PostgreSQL and embeddings from ChromaDB.
    """
    with get_sync_session() as db:
        require_conversation(db, session_id, current_user)
    success = document_memory.delete_document_cascade(doc_id=doc_id, session_id=session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted", "doc_id": doc_id, "session_id": session_id}
