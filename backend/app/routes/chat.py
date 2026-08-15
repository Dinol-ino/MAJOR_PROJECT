import time
import logging
from typing import List, Dict, Any
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

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

# Instantiate controllers
input_guard = Layer1InputGuard()
trusted_context = Layer2TrustedContext()
output_guard = Layer3OutputGuard()
audit_logger = AuditLogger(settings.SQLITE_DB_PATH)

tier1_retriever = Tier1LawRetrieval(settings.CHROMA_PERSIST_DIR)
tier2_retriever = Tier2UserRetrieval(settings.CHROMA_PERSIST_DIR)

context_builder = ContextBuilder()
token_budget_manager = TokenBudgetManager()
citation_builder = CitationBuilder()
hallucination_detector = HallucinationDetector()
confidence_scorer = ConfidenceScorer()
response_formatter = ResponseFormatter()

# In-memory store for active session titles
_session_registry: Dict[str, Dict[str, Any]] = {}


@router.get("/chat/sessions")
def list_sessions():
    """
    Returns list of past task sessions for the sidebar navigation.
    """
    sessions = []
    for sid, meta in _session_registry.items():
        sessions.append({
            "session_id": sid,
            "title": meta.get("title", f"Task {sid}"),
            "created_at": meta.get("created_at"),
            "model": meta.get("model", "qwen2.5:3b"),
        })
    return {"sessions": list(reversed(sessions))}


@router.delete("/chat/sessions/{session_id}")
def delete_session(session_id: str):
    if session_id in _session_registry:
        del _session_registry[session_id]
    return {"status": "ok", "deleted": session_id}


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    start_time = time.time()
    
    # Track session in registry for Sidebar
    if request.session_id not in _session_registry:
        title = request.message[:35] + ("..." if len(request.message) > 35 else "")
        _session_registry[request.session_id] = {
            "title": title,
            "created_at": "Just now",
            "model": request.model or settings.DEFAULT_MODEL,
        }

    # --- SHIELD ON PIPELINE (Defensive RAG Mode) ---
    if request.shield_on:
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
            return ChatResponse(
                answer=f"Query blocked by Security Shield: {reason}",
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

        # Invoke Stage 5 Runtime Abstraction Engine
        runtime = RuntimeManager.get()
        try:
            raw_answer = await runtime.generate(prompt, model=request.model)
        except Exception as exc:
            logger.error(f"Runtime engine generation error: {exc}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"Runtime engine generation error: {str(exc)}")

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
            return ChatResponse(
                answer=f"Response quarantined: {error_reason}",
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
