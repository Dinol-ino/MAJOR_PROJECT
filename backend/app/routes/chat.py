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
                shield_on=True
            )
            durable_memory.add_message(
                conversation_id=request.session_id,
                role="assistant",
                content=orch_res.answer,
                citations=orch_res.sources,
                user_id="default_user"
            )
            return ChatResponse(
                answer=orch_res.answer,
                sources=orch_res.sources,
                blocked_by=orch_res.blocked_by,
                block_reason=orch_res.block_reason
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
                block_reason=reason
            )

        # Retrieval Engine (Tier 1 Statutory + Tier 2 User Documents)
        t1_results = tier1_retriever.query(request.message)
        t2_results = tier2_retriever.query(request.session_id, request.message)
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

        # Layer 2: Secure Prompt Construction (with Presidio PII anonymization)
        prompt = trusted_context.build_prompt(request.message, fitted_chunks)

        # Invoke Stage 5 Runtime Abstraction Engine with automatic OOM fallback
        runtime = RuntimeManager.get()
        target_model = request.model or settings.DEFAULT_MODEL
        try:
            raw_answer = await runtime.generate(prompt, model=target_model)
        except Exception as exc:
            # Determine a real fallback model — never fall back to the same model that just failed
            fallback_model = settings.OLLAMA_FALLBACK_MODEL.strip() or settings.DEFAULT_MODEL
            if fallback_model.lower() == target_model.lower():
                # If configured fallback is same as primary, try default model if different
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
            if fallback_model:
                try:
                    raw_answer = await runtime.generate(prompt, model=fallback_model)
                except Exception as fallback_exc:
                    logger.error(f"Fallback to '{fallback_model}' also failed: {fallback_exc}", exc_info=True)
                    raise HTTPException(status_code=502, detail=f"Model generation error on both primary ('{target_model}') and fallback ('{fallback_model}') tiers: {str(fallback_exc)}")
            else:
                raise HTTPException(status_code=502, detail=f"Model generation error on '{target_model}' and no viable fallback model available: {str(exc)}")


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
                block_reason=error_reason
            )

        clean_answer = output_guard.last_clean_answer
        formatted_answer = response_formatter.format(clean_answer)

        # Verification & Scoring
        hallucination_report = hallucination_detector.detect(formatted_answer, fitted_chunks)
        confidence = confidence_scorer.score(formatted_answer, fitted_chunks, hallucination_report)

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

        sources_dict = [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in sources]
        durable_memory.add_message(
            conversation_id=request.session_id,
            role="assistant",
            content=formatted_answer,
            citations=sources_dict,
            user_id="default_user"
        )

        return ChatResponse(
            answer=formatted_answer,
            sources=sources,
            blocked_by=None,
            block_reason=None,
            confidence_score=confidence,
            hallucination_flags=hallucination_report.signals
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
