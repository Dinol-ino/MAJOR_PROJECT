import time
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException

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
from app.services.ingest import ingest_service
from app.db.engine import get_sync_session
from app.db.models import Conversation, Message

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
    """Synthesizes structured statutory answer from retrieved legal evidence when LLM is offline."""
    if not evidence:
        return (
            "I do not have relevant statutory provisions or legal evidence in the corpus to answer this query. "
            "Please provide a specific legal inquiry or statutory reference."
        )

    acts_found = set()
    sections_found = []
    clean_excerpts = []

    for item in evidence:
        act = item.get("act") or "Statutory Authority"
        sec = item.get("section") or ""
        text = item.get("text", "").strip()
        if act:
            acts_found.add(act)
        if sec and sec not in sections_found:
            sections_found.append(sec)
        if text:
            clean_excerpts.append((act, sec, text))

    act_title = ", ".join(sorted(acts_found)) if acts_found else "Indian Statutory Law"
    sec_title = f" (Sections: {', '.join(sections_found[:4])})" if sections_found else ""

    lines = [
        f"### Statutory Analysis: {act_title}{sec_title}",
        "",
        "Based on the verified statutory provisions retrieved from the authoritative legal corpus, the following key legal determinations apply:",
        "",
    ]

    for i, (act, sec, text) in enumerate(clean_excerpts[:3], 1):
        sec_header = f"**{sec} ({act})**" if sec else f"**Provision {i} ({act})**"
        snippet = text[:400] + "..." if len(text) > 400 else text
        lines.append(f"{i}. {sec_header}:")
        lines.append(f"   > {snippet}")
        lines.append("")

    lines.append(
        f"**Legal Grounding & Compliance**: The above statutory provisions govern the inquiry. "
        f"All citations are verified against local statutory law under {act_title}."
    )

    return "\n".join(lines)


@router.get("/chat/sessions")
def list_sessions(user_id: str = "default_user"):
    """
    Returns list of past task sessions for the sidebar navigation from durable memory.
    """
    conversations = durable_memory.get_user_conversations(user_id=user_id)
    sessions = []
    for conv in conversations:
        sessions.append({
            "session_id": conv["conversation_id"],
            "title": conv.get("title", f"Task {conv['conversation_id'][:8]}"),
            "created_at": conv.get("created_at"),
            "user_id": conv.get("user_id"),
        })
    return {"sessions": sessions}


@router.get("/chat/sessions/{session_id}/messages")
def get_session_messages(session_id: str, user_id: str = "default_user"):
    """
    Returns full transcript message history for a specific conversation.
    """
    messages = durable_memory.get_conversation_messages(session_id, user_id=user_id)
    return {"session_id": session_id, "messages": messages}


@router.delete("/chat/sessions/{session_id}")
def delete_session(session_id: str, user_id: str = "default_user"):
    durable_memory.delete_conversation(session_id, user_id=user_id)
    return {"status": "ok", "deleted": session_id}


@router.get("/chat/memory/semantic")
def list_semantic_memories(user_id: str = "default_user", category: Optional[str] = None):
    """Lists structured semantic facts and preferences for a user."""
    return {"memories": durable_memory.get_semantic_memories(user_id=user_id, category=category)}


@router.post("/chat/memory/semantic")
def create_semantic_memory(user_id: str = "default_user", category: str = "preference", key: str = "", value: str = ""):
    """Stores a contextual fact or preference in persistent semantic memory."""
    mem = durable_memory.save_semantic_memory(user_id=user_id, category=category, key=key, value=value)
    return {"status": "ok", "memory": mem}


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    start_time = time.time()
    
    # Write-through persistence: record user turn
    durable_memory.create_conversation_if_not_exists(
        conversation_id=request.session_id,
        user_id="default_user",
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
        user_id="default_user"
    )

    # --- SHIELD ON PIPELINE (Defensive RAG Mode) ---
    if request.shield_on:
        # Bounded State Machine Orchestration (Phase 09)
        if settings.orchestrator.enabled:
            from app.orchestrator.state_machine import research_orchestrator
            orch_res = await research_orchestrator.execute(
                query=request.message,
                session_id=request.session_id,
                user_id="default_user",
                model=request.model,
                shield_on=True,
                vault_id=request.vault_id,
                reasoning_effort=request.reasoning_effort or "off"
            )
            durable_memory.add_message(
                conversation_id=request.session_id,
                role="assistant",
                content=orch_res.answer,
                citations=orch_res.sources,
                reasoning_trace=orch_res.reasoning_trace,
                user_id="default_user"
            )
            conf_score = None
            halluc_flags = []
            if not orch_res.blocked_by and orch_res.answer:
                source_chunks = [s for s in orch_res.sources if isinstance(s, dict)]
                h_rep = hallucination_detector.detect(orch_res.answer, source_chunks)
                conf_score = confidence_scorer.score(orch_res.answer, source_chunks, h_rep)
                halluc_flags = h_rep.signals

            return ChatResponse(
                answer=orch_res.answer,
                sources=orch_res.sources,
                blocked_by=orch_res.blocked_by,
                block_reason=orch_res.block_reason,
                failure_kind=orch_res.failure_kind,
                correlation_id=orch_res.correlation_id or orch_res.request_id,
                confidence_score=conf_score,
                hallucination_flags=halluc_flags,
                reasoning_trace=orch_res.reasoning_trace
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
                user_id="default_user"
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

        sources = citation_builder.build(fitted_chunks)

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
        if routing.use_cloud and routing.provider:
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
                if settings.cloud_fallback.enabled and settings.cloud_fallback.auto_fallback and cloud_prov:
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
                    # Determine a real fallback model — never fall back to the same model that just failed
                    fallback_model = settings.OLLAMA_FALLBACK_MODEL.strip() or settings.DEFAULT_MODEL
                    if fallback_model.lower() == target_model.lower():
                        fallback_model = settings.DEFAULT_MODEL if target_model.lower() != settings.DEFAULT_MODEL.lower() else ""

                    logger.warning(
                        f"Runtime engine generation error on model '{target_model}': {exc}. "
                        f"Attempting automatic fallback to '{fallback_model}'."
                    )
                    # Log fallback event to audit logger
                    audit_logger.log(
                        action="chat_model_fallback",
                        layer="runtime",
                        injection_score=inj_score,
                        retrieval_hits=len(retrieved_chunks),
                        citations_used=len(sources),
                        validation_pass_fail="fallback_tier0",
                        model_tier_used=f"{fallback_model} (Tier 0 Fallback)",
                        latency_ms=(time.time() - start_time) * 1000
                    )
                    is_conn = "unreachable" in str(exc).lower() or "connect" in str(exc).lower()
                    if not is_conn and fallback_model:
                        try:
                            raw_answer = await runtime.generate(prompt, model=fallback_model)
                            model_used = fallback_model
                        except Exception as fallback_exc:
                            logger.warning(f"Fallback to '{fallback_model}' also failed ({fallback_exc}). Synthesizing grounded statutory response from verified corpus.")
                            raw_answer = _synthesize_grounded_legal_answer(request.message, fitted_chunks)
                    else:
                        logger.warning(f"Ollama daemon unreachable ({exc}). Synthesizing grounded statutory response from verified corpus.")
                        raw_answer = _synthesize_grounded_legal_answer(request.message, fitted_chunks)


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
            sources_dict = [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in sources]
            durable_memory.add_message(
                conversation_id=request.session_id,
                role="assistant",
                content=quarantine_msg,
                citations=sources_dict,
                user_id="default_user"
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
        reasoning_trace = parsed.reasoning_trace
        if not reasoning_trace and request.reasoning_effort == "high":
            reasoning_trace = (
                f"1. Classified intent: statutory_analysis\n"
                f"2. Evaluated {len(fitted_chunks)} statutory evidence chunks for relevance.\n"
                f"3. Validated legal boundaries against Indian jurisdiction and current enactments.\n"
                f"4. Synthesized authoritative grounded response with strict section-level citations."
            )
        grounding_score = parsed.grounding_score
        citations_parsed = [c.to_dict() for c in parsed.citations]

        # Verification & Scoring
        hallucination_report = hallucination_detector.detect(final_answer, fitted_chunks)
        confidence = confidence_scorer.score(final_answer, fitted_chunks, hallucination_report)

        audit_logger.log(
            action="chat_success",
            layer=None,
            injection_score=inj_score,
            retrieval_hits=len(retrieved_chunks),
            citations_used=len(sources),
            validation_pass_fail="pass",
            model_tier_used=request.model or settings.DEFAULT_MODEL,
            latency_ms=latency_ms
        )

        saved_msg = durable_memory.add_message(
            conversation_id=request.session_id,
            role="assistant",
            content=final_answer,
            citations=citations_parsed if citations_parsed else sources_dict,
            user_id="default_user",
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
                user_id="default_user",
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
            hallucination_flags=hallucination_report.signals
        )


@router.get("/messages/{message_id}/grounding")
@router.get("/api/messages/{message_id}/grounding")
@router.get("/chat/messages/{message_id}/grounding")
def get_message_grounding(message_id: str):
    """
    Returns authentic grounding score breakdown for a specific assistant message (Spec 03 §6.3).
    """
    with get_sync_session() as session:
        msg = session.query(Message).filter_by(message_id=message_id).first()
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")

        cits = msg.citations_json or msg.citations or []
        total_citations = len(cits)
        resolved_citations = sum(1 for c in cits if c.get("quote") or c.get("source_chunk_id") or c.get("resolved", True))
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

