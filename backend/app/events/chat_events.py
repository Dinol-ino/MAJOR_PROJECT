import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.defense.audit_log import AuditLogger
from app.services.citation_graph_service import citation_graph_service
from app.memory.research_memory import research_memory
from app.db.engine import get_sync_session
from app.db.models import Statute, StatuteSection

logger = logging.getLogger(__name__)
audit_logger = AuditLogger()


@dataclass
class ChatResponseFinalized:
    """
    Internal event emitted once per completed /chat or orchestration call.
    Encapsulates all necessary execution context to drive independent downstream read models.
    """
    conversation_id: str
    message_id: str
    user_id: str
    query: str
    answer: str
    citations: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    model_used: str = "qwen2.5:3b"
    runtime_used: str = "local"
    reasoning_trace: Optional[str] = None
    grounding_score: Optional[float] = None
    injection_score: float = 0.0
    retrieval_hits: int = 0
    latency_ms: float = 0.0
    is_deep_thinking: bool = False
    vault_id: Optional[str] = None
    blocked_by: Optional[str] = None
    block_reason: Optional[str] = None
    failure_kind: Optional[str] = None


def handle_audit_log(event: ChatResponseFinalized) -> None:
    """Handler 1: Appends hash-chained audit record to L6 Cryptographic Audit Ledger."""
    try:
        validation_pass_fail = "blocked" if event.blocked_by else ("insufficient_evidence" if event.failure_kind == "insufficient_evidence" else "pass")
        action = f"chat_{event.blocked_by}_blocked" if event.blocked_by else ("chat_insufficient_evidence" if event.failure_kind == "insufficient_evidence" else "chat_completed")

        audit_logger.log(
            action=action,
            layer=event.blocked_by or ("orchestrator" if event.failure_kind else "layer3"),
            injection_score=event.injection_score,
            retrieval_hits=event.retrieval_hits,
            citations_used=len(event.citations),
            validation_pass_fail=validation_pass_fail,
            model_tier_used=f"{event.model_used} ({event.runtime_used})",
            latency_ms=event.latency_ms
        )
    except Exception as exc:
        logger.warning(f"Audit log event handler warning: {exc}")


def handle_citation_graph(event: ChatResponseFinalized) -> None:
    """Handler 2: Upserts citation nodes/edges into CitationGraphService for verified citations."""
    if not event.citations or event.blocked_by:
        return

    try:
        citation_graph_service.record_citations(
            conversation_id=event.conversation_id,
            message_id=event.message_id,
            citations=event.citations
        )
    except Exception as exc:
        logger.warning(f"Citation graph event handler warning: {exc}")


def handle_research_memory(event: ChatResponseFinalized) -> None:
    """Handler 3: Persists L5 Research Session Memory only if part of a Deep Thinking multi-step trace."""
    if not event.is_deep_thinking or not event.reasoning_trace or event.blocked_by:
        return

    try:
        topic = event.query[:100] + ("..." if len(event.query) > 100 else "")
        findings = f"{event.reasoning_trace}\n\n---\n\n{event.answer}"
        research_memory.update_findings(
            session_id=event.conversation_id,
            findings=findings,
            citations=event.citations,
            status="completed"
        )
    except Exception as exc:
        logger.warning(f"Research memory event handler warning: {exc}")


def handle_statute_reference(event: ChatResponseFinalized) -> None:
    """Handler 4: Bumps updated_at on cited statutes in the library for active referencing."""
    if not event.citations or event.blocked_by:
        return

    try:
        with get_sync_session() as session:
            act_slugs = set()
            for cit in event.citations:
                act_slug = cit.get("act_slug") or (cit.get("act", "").lower().replace(" ", "_").replace(",", ""))
                if act_slug:
                    act_slugs.add(act_slug)

            if act_slugs:
                now = datetime.utcnow()
                statutes = session.query(Statute).filter(Statute.slug.in_(act_slugs)).all()
                for st in statutes:
                    st.updated_at = now
                session.commit()
    except Exception as exc:
        logger.warning(f"Statute reference event handler warning: {exc}")


# Registry of active event handlers
_EVENT_HANDLERS = [
    handle_audit_log,
    handle_citation_graph,
    handle_research_memory,
    handle_statute_reference,
]


def emit_chat_response_finalized(event: ChatResponseFinalized) -> None:
    """
    Dispatches ChatResponseFinalized to all registered handlers with error isolation.
    """
    for handler in _EVENT_HANDLERS:
        try:
            handler(event)
        except Exception as err:
            logger.error(f"Error in chat event handler {handler.__name__}: {err}", exc_info=True)
