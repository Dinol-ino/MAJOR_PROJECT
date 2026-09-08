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


# ---------------------------------------------------------
# Event Data Structures (Module 9 §9.2)
# ---------------------------------------------------------

@dataclass
class ChatResponseFinalized:
    """
    Event 1: Emitted by /chat and /chat/stream when a legal response is finalized.
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


@dataclass
class DocumentIngested:
    """
    Event 2: Emitted by /upload and /upload/batch on PDF document ingestion.
    """
    doc_id: str
    session_id: str
    filename: str
    file_size_bytes: int
    chunk_count: int
    vault_id: Optional[str] = None
    pages_count: int = 1
    citations_found: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MCPToolInvoked:
    """
    Event 3: Emitted by /mcp/tool-call on Model Context Protocol tool execution.
    """
    tool_name: str
    category: str
    network_mode: str
    is_allowed: bool
    arguments: Dict[str, Any] = field(default_factory=dict)
    output_preview: Optional[str] = None
    latency_ms: float = 0.0
    session_id: Optional[str] = None
    precedents_found: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DefenseLayerDecision:
    """
    Event 4: Emitted by Layer 1/2/3 defense layers for every query evaluation.
    """
    layer_name: str
    passed: bool
    injection_score: float = 0.0
    block_reason: Optional[str] = None
    latency_ms: float = 0.0
    session_id: Optional[str] = None


@dataclass
class ModelLifecycleChanged:
    """
    Event 5: Emitted on model pulling, runtime switching, or recommendation overrides.
    """
    event_type: str  # "pull" | "switch" | "override" | "reset"
    model_name: str
    runtime_name: Optional[str] = None
    previous_model: Optional[str] = None
    source: str = "user"
    session_id: Optional[str] = None
    status: str = "active"


# ---------------------------------------------------------
# Event Handlers (Safe & Isolated Execution)
# ---------------------------------------------------------

# Chat handlers
def handle_chat_audit_log(event: ChatResponseFinalized) -> None:
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
        logger.warning(f"Chat audit log handler error: {exc}")


def handle_chat_citation_graph(event: ChatResponseFinalized) -> None:
    if not event.citations or event.blocked_by:
        return
    try:
        citation_graph_service.record_citations(
            conversation_id=event.conversation_id,
            message_id=event.message_id,
            citations=event.citations
        )
    except Exception as exc:
        logger.warning(f"Chat citation graph handler error: {exc}")


def handle_chat_research_memory(event: ChatResponseFinalized) -> None:
    if not event.is_deep_thinking or not event.reasoning_trace or event.blocked_by:
        return
    try:
        findings = f"{event.reasoning_trace}\n\n---\n\n{event.answer}"
        research_memory.update_findings(
            session_id=event.conversation_id,
            findings=findings,
            citations=event.citations,
            status="completed"
        )
    except Exception as exc:
        logger.warning(f"Chat research memory handler error: {exc}")


def handle_chat_statute_reference(event: ChatResponseFinalized) -> None:
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
        logger.warning(f"Chat statute reference handler error: {exc}")


# Document Ingestion handlers
def handle_document_audit_log(event: DocumentIngested) -> None:
    try:
        audit_logger.log(
            action=f"upload_pdf:{event.filename}",
            layer="persistence",
            retrieval_hits=event.chunk_count,
            validation_pass_fail="pass"
        )
    except Exception as exc:
        logger.warning(f"Document audit handler error: {exc}")


def handle_document_citation_graph(event: DocumentIngested) -> None:
    if not event.citations_found:
        return
    try:
        citation_graph_service.record_citations(
            conversation_id=event.session_id,
            message_id=event.doc_id,
            citations=event.citations_found,
            derivation_method="user_document_reference"
        )
    except Exception as exc:
        logger.warning(f"Document citation graph handler error: {exc}")


# MCP Tool Invocation handlers
def handle_mcp_audit_log(event: MCPToolInvoked) -> None:
    try:
        audit_logger.log(
            action=f"mcp_tool_call:{event.tool_name}",
            layer="mcp_gateway",
            validation_pass_fail="pass" if event.is_allowed else "blocked_policy",
            latency_ms=event.latency_ms
        )
    except Exception as exc:
        logger.warning(f"MCP audit handler error: {exc}")


def handle_mcp_citation_graph(event: MCPToolInvoked) -> None:
    if not event.precedents_found:
        return
    try:
        citation_graph_service.record_citations(
            conversation_id=event.session_id or "mcp_session",
            message_id=f"mcp_{event.tool_name}",
            citations=event.precedents_found,
            derivation_method="mcp_case_law_lookup"
        )
    except Exception as exc:
        logger.warning(f"MCP citation graph handler error: {exc}")


# Defense Layer Decision handler
def handle_defense_decision_audit(event: DefenseLayerDecision) -> None:
    try:
        action = f"defense_{event.layer_name}_{'passed' if event.passed else 'blocked'}"
        audit_logger.log(
            action=action,
            layer=event.layer_name,
            injection_score=event.injection_score,
            validation_pass_fail="pass" if event.passed else "fail",
            latency_ms=event.latency_ms
        )
    except Exception as exc:
        logger.warning(f"Defense decision audit handler error: {exc}")


# Model Lifecycle handler
def handle_model_lifecycle_audit(event: ModelLifecycleChanged) -> None:
    try:
        audit_logger.log(
            action=f"model_{event.event_type}:{event.model_name}",
            layer="runtime_manager",
            model_tier_used=f"{event.model_name} ({event.runtime_name or 'local'})",
            validation_pass_fail=event.status
        )
    except Exception as exc:
        logger.warning(f"Model lifecycle audit handler error: {exc}")


# ---------------------------------------------------------
# Event Bus Emitters
# ---------------------------------------------------------

_CHAT_HANDLERS = [handle_chat_audit_log, handle_chat_citation_graph, handle_chat_research_memory, handle_chat_statute_reference]
_DOC_HANDLERS = [handle_document_audit_log, handle_document_citation_graph]
_MCP_HANDLERS = [handle_mcp_audit_log, handle_mcp_citation_graph]
_DEFENSE_HANDLERS = [handle_defense_decision_audit]
_MODEL_HANDLERS = [handle_model_lifecycle_audit]


def emit_chat_response_finalized(event: ChatResponseFinalized) -> None:
    for h in _CHAT_HANDLERS:
        try:
            h(event)
        except Exception as e:
            logger.error(f"Error in chat handler {h.__name__}: {e}", exc_info=True)


def emit_document_ingested(event: DocumentIngested) -> None:
    for h in _DOC_HANDLERS:
        try:
            h(event)
        except Exception as e:
            logger.error(f"Error in doc handler {h.__name__}: {e}", exc_info=True)


def emit_mcp_tool_invoked(event: MCPToolInvoked) -> None:
    for h in _MCP_HANDLERS:
        try:
            h(event)
        except Exception as e:
            logger.error(f"Error in mcp handler {h.__name__}: {e}", exc_info=True)


def emit_defense_layer_decision(event: DefenseLayerDecision) -> None:
    for h in _DEFENSE_HANDLERS:
        try:
            h(event)
        except Exception as e:
            logger.error(f"Error in defense handler {h.__name__}: {e}", exc_info=True)


def emit_model_lifecycle_changed(event: ModelLifecycleChanged) -> None:
    for h in _MODEL_HANDLERS:
        try:
            h(event)
        except Exception as e:
            logger.error(f"Error in model handler {h.__name__}: {e}", exc_info=True)
