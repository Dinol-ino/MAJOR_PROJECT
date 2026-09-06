from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel, Field

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
    user_id: str = Query("default_user", description="Authenticated user ID"),
    category: Optional[str] = Query(None, description="Optional category filter")
):
    """
    Transparency requirement: lists a user's explicit semantic memory entries.
    """
    memories = semantic_memory.get_user_memories(user_id=user_id, category=category)
    return {"user_id": user_id, "count": len(memories), "memories": memories}


@router.post("/semantic")
def propose_semantic_memory(
    proposal: SemanticMemoryProposal,
    user_id: str = Query("default_user", description="Authenticated user ID")
):
    """
    Proposes a semantic fact/preference. Runs through the strict L3 Validation Gate.
    """
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal memory error: {exc}")


@router.delete("/semantic/{memory_id}")
def delete_semantic_memory(
    memory_id: str,
    user_id: str = Query("default_user", description="Authenticated user ID")
):
    """
    Explicit user-initiated deletion of an L3 semantic memory entry.
    """
    try:
        success = semantic_memory.delete_memory(memory_id=memory_id, user_id=user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        return {"status": "deleted", "memory_id": memory_id}
    except PermissionError as p_err:
        raise HTTPException(status_code=403, detail=str(p_err))


@router.get("/research/{session_id}")
def get_research_session(session_id: str):
    """
    Retrieves an L5 research session's findings, provenance sources, and citations.
    """
    session_data = research_memory.get_research_session(session_id=session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Research session not found")
    return session_data


@router.delete("/documents/{doc_id}")
def delete_document_cascade(
    doc_id: str,
    session_id: str = Query(..., description="Session identifier for the document")
):
    """
    L4 Deletion Cascade: removes document metadata from PostgreSQL and embeddings from ChromaDB.
    """
    success = document_memory.delete_document_cascade(doc_id=doc_id, session_id=session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted", "doc_id": doc_id, "session_id": session_id}
