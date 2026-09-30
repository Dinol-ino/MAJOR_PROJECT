import time
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from app.routes.auth import get_current_user

from app.schemas import ChatRequest, ChatResponse
from app.config import settings
from app.defense.layer1_input_guard import Layer1InputGuard
from app.defense.layer2_trusted_context import Layer2TrustedContext
from app.defense.layer3_output_guard import Layer3OutputGuard
from app.defense.audit_log import AuditLogger
from app.retrieval.tier1_law import Tier1LawRetrieval
from app.retrieval.tier2_user import Tier2UserRetrieval
from app.retrieval.hybrid_rank import fuse_bm25_dense

# Stage 5 Runtime Modules
from app.runtime.runtime_manager import RuntimeManager
from app.runtime.context_builder import ContextBuilder
from app.runtime.token_budget_manager import TokenBudgetManager
from app.runtime.citation_builder import CitationBuilder
from app.runtime.hallucination_detector import HallucinationDetector
from app.runtime.confidence_scorer import ConfidenceScorer
from app.runtime.response_formatter import ResponseFormatter

from app.memory.durable_memory import DurableMemoryManager
from app.memory.request_memory import RequestMemory
from app.services.ingest import ingest_service
from app.db.engine import get_sync_session
from app.db.models import Conversation, Message
from app.security.ownership import current_user_id, conversation_accessible, require_vault, owns

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

# Instantiate controllers
input_guard = Layer1InputGuard()
trusted_context = Layer2TrustedContext()
output_guard = Layer3OutputGuard()
audit_logger = AuditLogger()
durable_memory = DurableMemoryManager()

tier1_retriever = Tier1LawRetrieval(settings.CHROMA_PERSIST_DIR)
tier2_retriever = Tier2UserRetrieval(settings.CHROMA_PERSIST_DIR)

context_builder = ContextBuilder()
token_budget_manager = TokenBudgetManager()
citation_builder = CitationBuilder()
hallucination_detector = HallucinationDetector()
confidence_scorer = ConfidenceScorer()
response_formatter = ResponseFormatter()
 
def _synthesize_grounded_legal_answer(query: str, evidence: List[Dict[str, Any]]) -> str:
    """Evidence-only reply used when the model is unavailable (shared with the orchestrator; no analysis claimed)."""
    from app.orchestrator.state_machine import research_orchestrator
    return research_orchestrator._synthesize_grounded_answer(query, evidence)


@router.get("/chat/sessions")
def list_sessions(current_user: Dict = Depends(get_current_user)):
    """
    Returns list of past task sessions for the sidebar navigation from durable memory.
    """
    uid = current_user_id(current_user)
    conversations = durable_memory.get_user_conversations(user_id=uid)
    sessions = []
    for conv in conversations:
        sessions.append({
            "session_id": conv["conversation_id"],
            "title": conv.get("title", f"Task {conv['conversation_id'][:8]}"),
            "created_at": conv.get("created_at"),
            "user_id": conv.get("user_id"),
            # The sidebar could not group chats under their vault without this, so a
            # vault always looked like an empty folder. Additive field; existing
            # consumers are unaffected.
            "project_vault_id": conv.get("project_vault_id"),
        })
    return {"sessions": sessions}


@router.get("/chat/sessions/{session_id}/messages")
def get_session_messages(session_id: str, current_user: Dict = Depends(get_current_user)):
    """
    Returns full transcript message history for a specific conversation.
    """
    uid = current_user_id(current_user)
    messages = durable_memory.get_conversation_messages(session_id, user_id=uid)
    return {"session_id": session_id, "messages": messages}


@router.delete("/chat/sessions/{session_id}")
def delete_session(session_id: str, current_user: Dict = Depends(get_current_user)):
    uid = current_user_id(current_user)
    durable_memory.delete_conversation(session_id, user_id=uid)
    return {"status": "ok", "deleted": session_id}


@router.get("/chat/memory/semantic")
def list_semantic_memories(category: Optional[str] = None, current_user: Dict = Depends(get_current_user)):
    """Lists structured semantic facts and preferences for the authenticated user."""
    uid = current_user_id(current_user)
    return {"memories": durable_memory.get_semantic_memories(user_id=uid, category=category)}


@router.post("/chat/memory/semantic")
def create_semantic_memory(category: str = "preference", key: str = "", value: str = "", current_user: Dict = Depends(get_current_user)):
    """Stores a contextual fact or preference in persistent semantic memory."""
    uid = current_user_id(current_user)
    mem = durable_memory.save_semantic_memory(user_id=uid, category=category, key=key, value=value)
    return {"status": "ok", "memory": mem}


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, current_user: Dict = Depends(get_current_user)):
    start_time = time.time()
    current_uid = current_user_id(current_user)

    # Isolation: the session id and vault id are client-supplied, so bind them to the caller.
    with get_sync_session() as session:
        if not conversation_accessible(session, request.session_id, current_user):
            raise HTTPException(status_code=404, detail="Conversation not found.")
        if request.vault_id:
            require_vault(session, request.vault_id, current_user)

    # Layers 1-3 are mandatory. The unshielded baseline exists only for offline evaluation.
    if not request.shield_on and not settings.security.allow_unshielded_baseline:
        request.shield_on = True

    if len(request.message or "") > settings.security.max_query_chars * 4:
        raise HTTPException(status_code=413, detail="Message is too long.")

    # The answering model is decided once, explicitly. It is never silently swapped later.
    from app.runtime.model_state import model_state, ModelNotAvailable
    try:
        resolved_model = await model_state.resolve_for_request(request.model)
    except ModelNotAvailable as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)})
    request.model = resolved_model

    req_memory = RequestMemory(
        session_id=request.session_id,
        raw_query=request.message,
        model_name=request.model or settings.DEFAULT_MODEL
    )
    
    # Write-through persistence: record user turn
    durable_memory.create_conversation_if_not_exists(
        conversation_id=request.session_id,
        user_id=current_uid,
        title=request.message[:35] + ("..." if len(request.message) > 35 else "")
    )
    if request.vault_id:
        try:
            with get_sync_session() as session:
                conv = session.query(Conversation).filter_by(conversation_id=request.session_id).first()
                if conv and not conv.project_vault_id:
                    conv.project_vault_id = request.vault_id
        except Exception as e:
            logger.debug(f"Vault binding deferred: {e}")

    durable_memory.add_message(
        conversation_id=request.session_id,
        role="user",
        content=request.message,
        user_id=current_uid
    )

    # --- SHIELD ON PIPELINE (Defensive RAG Mode) ---
    if request.shield_on:
        # Bounded State Machine Orchestration (Phase 09)
        if settings.orchestrator.enabled:
            from app.orchestrator.state_machine import research_orchestrator
            orch_res = await research_orchestrator.execute(
                query=request.message,
                session_id=request.session_id,
                user_id=current_uid,
                model=resolved_model,
                shield_on=True,
                vault_id=request.vault_id,
                reasoning_effort=request.reasoning_effort or "medium"
            )
            durable_memory.add_message(
                conversation_id=request.session_id,
                role="assistant",
                content=orch_res.answer,
                citations=orch_res.sources,
                reasoning_trace=orch_res.reasoning_trace,
                user_id=current_uid
            )
            # No synthetic "confidence" number is reported: the previous formula mostly measured
            # whether any evidence existed. Hallucination signals (concrete checks) are still returned.
            conf_score = None
            halluc_flags = []
            if not orch_res.blocked_by and orch_res.answer and orch_res.failure_kind != "model_unavailable":
                source_chunks = [s for s in orch_res.sources if isinstance(s, dict)]
                halluc_flags = hallucination_detector.detect(orch_res.answer, source_chunks).signals

            req_memory.record_defense_event(
                layer="orchestrator",
                passed=not bool(orch_res.blocked_by),
                details={"failure_kind": orch_res.failure_kind, "correlation_id": orch_res.correlation_id or orch_res.request_id}
            )
            req_memory.mark_completed()

            return ChatResponse(
                answer=orch_res.answer,
                sources=orch_res.sources,
                blocked_by=orch_res.blocked_by,
                block_reason=orch_res.block_reason,
                failure_kind=orch_res.failure_kind,
                correlation_id=orch_res.correlation_id or orch_res.request_id,
                confidence_score=conf_score,
                grounding_score=orch_res.grounding_score,
                citations_parsed=orch_res.citations_parsed,
                hallucination_flags=halluc_flags,
                reasoning_trace=orch_res.reasoning_trace,
                model_used=orch_res.model_used,
                runtime_used=orch_res.runtime_used or settings.MODEL_RUNTIME,
                metrics=orch_res.metrics,
            )

        # Direct Fallback Pipeline (Rollback Mode)
        # Layer 1: Input Guard Validation with query hash deduplication
        is_safe, reason, inj_score, q_hash = input_guard.validate_with_score(request.message)
        if not is_safe:
            latency_ms = (time.time() - start_time) * 1000
            audit_logger.log(
                action="chat_blocked_input",
                layer="layer1",
                injection_score=inj_score,
                retrieval_hits=0,
                citations_used=0,
                validation_pass_fail="blocked_input",
                model_tier_used=request.model or settings.DEFAULT_MODEL,
                latency_ms=latency_ms
            )
            blocked_msg = f"Query blocked by Security Shield: {reason}"
            durable_memory.add_message(
                conversation_id=request.session_id,
                role="assistant",
                content=blocked_msg,
                user_id=current_uid
            )
            return ChatResponse(
                answer=blocked_msg,
                sources=[],
                blocked_by="layer1",
                block_reason=reason,
                failure_kind="security_block",
                correlation_id=request.session_id
            )

        # Retrieval Engine (Tier 1 Statutory + Tier 2 User Documents + Vault Documents)
        t1_results = tier1_retriever.query(request.message)
        t2_results = tier2_retriever.query(request.session_id, request.message)

        # Vault-scoped document evidence (Spec 01 §5)
        active_vault_id = request.vault_id
        if not active_vault_id:
            try:
                with get_sync_session() as session:
                    conv = session.query(Conversation).filter_by(conversation_id=request.session_id).first()
                    if conv and conv.project_vault_id:
                        active_vault_id = conv.project_vault_id
            except Exception:
                pass
        if active_vault_id:
            vault_evidence = ingest_service.query_vault(active_vault_id, request.message, top_k=3)
            t2_results.extend(vault_evidence)

        retrieved_chunks = fuse_bm25_dense(t1_results, t2_results, top_k=5)

        # Context Builder & Token Budget Management
        context_pkg = context_builder.build(
            query=request.message,
            retrieved_chunks=retrieved_chunks
        )

        fitted_chunks, truncated_count = token_budget_manager.fit_chunks(
            base_prompt_tokens=context_pkg.token_count,
            chunks=context_pkg.chunks_included
        )

        from app.runtime import egress_guard
        if active_vault_id:
            egress_guard.mark_private_context("request is scoped to a vault")
        egress_guard.mark_private_from_chunks(fitted_chunks)
        sources = citation_builder.build(fitted_chunks)
        sources_dict = [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in sources]

        # Layer 2: Secure Prompt Construction (with Presidio PII anonymization & System Prompt v4)
        prompt = trusted_context.build_prompt(
            request.message,
            fitted_chunks,
            reasoning_effort=request.reasoning_effort
        )

        # Stage 5 Runtime Abstraction Engine with Circuit Breaker & Cloud Fallback
        from app.runtime.router import fallback_router
        from app.runtime.circuit_breaker import circuit_breaker
        from app.runtime.cloud_runtime import CloudRuntime

        runtime = RuntimeManager.get()
        target_model = request.model or settings.DEFAULT_MODEL
        model_used = target_model
        runtime_used = "local"

        routing = fallback_router.route_request(target_model)
        # Vault (client matter) evidence never leaves the machine, whatever the cloud settings.
        cloud_allowed = settings.cloud_fallback.enabled and not active_vault_id
        if cloud_allowed and routing.use_cloud and routing.provider:
            logger.info(f"Proactive cloud promotion: {routing.reason}")
            cloud_rt = CloudRuntime(provider=routing.provider)
            raw_answer = await cloud_rt.generate(prompt, model=routing.model)
            model_used = routing.model
            runtime_used = "cloud"
        else:
            try:
                raw_answer = await runtime.generate(prompt, model=target_model)
                circuit_breaker.record_success(target_model)
            except Exception as exc:
                kind = fallback_router.classify_failure(exc)
                circuit_breaker.record_failure(target_model, kind=kind, reason=str(exc))
                cloud_prov = fallback_router.resolve_cloud_provider()
                if cloud_allowed and settings.cloud_fallback.auto_fallback and cloud_prov:
                    cloud_model = (
                        settings.cloud_fallback.grok_model
                        if cloud_prov == "grok"
                        else settings.cloud_fallback.zai_model
                    )
                    logger.info(f"Promoting chat generation to CloudRuntime ({cloud_prov.title()}).")
                    cloud_rt = CloudRuntime(provider=cloud_prov)
                    raw_answer = await cloud_rt.generate(prompt, model=cloud_model)
                    model_used = cloud_model
                    runtime_used = "cloud"
                else:
                    # No silent substitution of another local model: report and show evidence only.
                    logger.warning("Model '%s' unavailable (%s); returning evidence excerpts only.", target_model, type(exc).__name__)
                    audit_logger.log(
                        action="chat_model_unavailable",
                        layer="runtime",
                        injection_score=inj_score,
                        retrieval_hits=len(retrieved_chunks),
                        citations_used=len(sources),
                        validation_pass_fail="model_unavailable",
                        model_tier_used=target_model,
                        latency_ms=(time.time() - start_time) * 1000
                    )
                    raw_answer = _synthesize_grounded_legal_answer(request.message, fitted_chunks)
                    model_used = "none"


        # Layer 3: Output Guard Validation & Citation-existence Check
        is_valid, error_reason = output_guard.validate(raw_answer, fitted_chunks, prompt)
        latency_ms = (time.time() - start_time) * 1000

        if not is_valid:
            audit_logger.log(
                action="chat_blocked_output",
                layer="layer3",
                injection_score=inj_score,
                retrieval_hits=len(retrieved_chunks),
                citations_used=len(sources),
                validation_pass_fail="blocked_output",
                model_tier_used=request.model or settings.DEFAULT_MODEL,
                latency_ms=latency_ms
            )
            quarantine_msg = f"Response quarantined: {error_reason}"
            durable_memory.add_message(
                conversation_id=request.session_id,
                role="assistant",
                content=quarantine_msg,
                citations=sources_dict,
                user_id=current_uid
            )
            return ChatResponse(
                answer=quarantine_msg,
                sources=sources,
                blocked_by="layer3",
                block_reason=error_reason,
                failure_kind="security_block",
                correlation_id=request.session_id
            )

        clean_answer = output_guard.last_clean_answer
        formatted_answer = response_formatter.format(clean_answer)

        # Spec 03: Parse <deep_thinking>, [^S:...] citations, and calculate authentic Grounding Score
        from app.services.response_parser import response_parser
        parsed = response_parser.parse(clean_answer, evidence_chunks=fitted_chunks)
        final_answer = parsed.content if parsed.content else formatted_answer
        # Only a trace actually emitted by the model is shown; none is fabricated.
        reasoning_trace = parsed.reasoning_trace
        grounding_score = parsed.grounding_score
        citations_parsed = [c.to_dict() for c in parsed.citations]

        # Verification & Scoring
        hallucination_report = hallucination_detector.detect(final_answer, fitted_chunks)
        confidence = confidence_scorer.score(final_answer, fitted_chunks, hallucination_report)

        runtime_used = runtime_used if runtime_used == "cloud" else settings.MODEL_RUNTIME

        audit_logger.log(
            action="chat_success",
            layer=None,
            injection_score=inj_score,
            retrieval_hits=len(retrieved_chunks),
            citations_used=len(sources),
            validation_pass_fail="pass",
            model_tier_used=model_used,
            latency_ms=latency_ms
        )

        saved_msg = durable_memory.add_message(
            conversation_id=request.session_id,
            role="assistant",
            content=final_answer,
            citations=citations_parsed if citations_parsed else sources_dict,
            user_id=current_uid,
            model_used=model_used,
            runtime_used=runtime_used,
            reasoning_trace=reasoning_trace,
            grounding_score=grounding_score
        )

        # Spec 04 §4.1: Emit ChatResponseFinalized internal event to all decoupled handlers
        try:
            from app.events.chat_events import ChatResponseFinalized, emit_chat_response_finalized
            msg_id = saved_msg.get("id") if isinstance(saved_msg, dict) else request.session_id
            event = ChatResponseFinalized(
                conversation_id=request.session_id,
                message_id=msg_id,
                user_id=current_uid,
                query=request.message,
                answer=final_answer,
                citations=citations_parsed if citations_parsed else [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in sources],
                sources=[s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in sources],
                model_used=model_used,
                runtime_used=runtime_used,
                reasoning_trace=reasoning_trace,
                grounding_score=grounding_score,
                injection_score=inj_score,
                retrieval_hits=len(retrieved_chunks),
                latency_ms=latency_ms,
                is_deep_thinking=request.reasoning_effort == "high",
                vault_id=active_vault_id,
                blocked_by=None,
                block_reason=None,
                failure_kind=None
            )
            emit_chat_response_finalized(event)
        except Exception as e:
            logger.warning(f"Event fanout notice in chat endpoint: {e}")

        return ChatResponse(
            answer=final_answer,
            sources=sources,
            blocked_by=None,
            block_reason=None,
            failure_kind=None,
            correlation_id=request.session_id,
            confidence_score=confidence,
            grounding_score=grounding_score,
            hallucination_flags=hallucination_report.signals,
            reasoning_trace=reasoning_trace,
            citations_parsed=citations_parsed,
            model_used=model_used,
            runtime_used=runtime_used
        )




    # --- SHIELD OFF PIPELINE (Unshielded Baseline) ---
    else:
        t1_results = tier1_retriever.query(request.message)
        t2_results = tier2_retriever.query(request.session_id, request.message)
        retrieved_chunks = fuse_bm25_dense(t1_results, t2_results, top_k=5)

        fitted_chunks, _ = token_budget_manager.fit_chunks(0, retrieved_chunks)
        sources = citation_builder.build(fitted_chunks)

        context_data = "\n\n".join([
            f"Act: {c.get('act', 'General Law')}, Section: {c.get('section', 'General')}\nText: {c.get('text', '')}"
            for c in fitted_chunks
        ])
        prompt = (
            f"You are a legal assistant. Context:\n{context_data}\n\n"
            f"Question: {request.message}\nAnswer:"
        )

        runtime = RuntimeManager.get()
        try:
            raw_answer = await runtime.generate(prompt, model=request.model)
        except Exception as exc:
            logger.error(f"Runtime engine generation error: {exc}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"Runtime engine generation error: {str(exc)}")

        formatted_answer = response_formatter.format(raw_answer)
        hallucination_report = hallucination_detector.detect(formatted_answer, fitted_chunks)
        confidence = confidence_scorer.score(formatted_answer, fitted_chunks, hallucination_report)

        return ChatResponse(
            answer=formatted_answer,
            sources=sources,
            blocked_by=None,
            block_reason=None,
            confidence_score=confidence,
            hallucination_flags=hallucination_report.signals,
            correlation_id=request.session_id,
            model_used=request.model or settings.DEFAULT_MODEL,
            runtime_used=settings.MODEL_RUNTIME
        )


@router.get("/messages/{message_id}/grounding")
@router.get("/api/messages/{message_id}/grounding")
@router.get("/chat/messages/{message_id}/grounding")
def get_message_grounding(message_id: str, current_user: Dict = Depends(get_current_user)):
    """
    Returns authentic grounding score breakdown for a specific assistant message (Spec 03 §6.3).
    """
    with get_sync_session() as session:
        msg = session.query(Message).filter_by(message_id=message_id).first()
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        conv = session.query(Conversation).filter_by(conversation_id=msg.conversation_id).first()
        if not conv or not owns(conv.user_id, current_user):
            raise HTTPException(status_code=404, detail="Message not found")

        cits = msg.citations_json or msg.citations or []
        total_citations = len(cits)
        resolved_citations = sum(1 for c in cits if c.get("quote") or c.get("source_chunk_id") or c.get("resolved") is True)
        unresolved = total_citations - resolved_citations

        return {
            "message_id": message_id,
            "grounding_score": msg.grounding_score,
            "total_citations": total_citations,
            "resolved_citations": resolved_citations,
            "unresolved_citations": unresolved,
            "penalties": {
                "unresolved_penalty": -15 if unresolved > 0 else 0,
                "uncited_penalty": -25 if total_citations == 0 else 0
            },
            "citations": cits
        }

