import time
import logging
from typing import Optional
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest
from app.runtime.manager import runtime_manager
from app.runtime.streaming import stream_token_generator
from app.memory.request_memory import RequestMemoryContainer
from app.defense.layer1_input_guard import Layer1InputGuard
from app.defense.layer2_trusted_context import Layer2TrustedContext
from app.defense.layer3_output_guard import Layer3OutputGuard
from app.defense.audit_log import AuditLogger
from app.retrieval.tier1_law import Tier1LawRetrieval
from app.retrieval.tier2_user import Tier2UserRetrieval
from app.retrieval.hybrid_rank import fuse_bm25_dense
from app.runtime.token_budget_manager import TokenBudgetManager
from app.runtime.context_builder import ContextBuilder
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["runtime"])

# Instantiations
input_guard = Layer1InputGuard()
trusted_context = Layer2TrustedContext()
output_guard = Layer3OutputGuard()
audit_logger = AuditLogger()
tier1_retriever = Tier1LawRetrieval(settings.CHROMA_PERSIST_DIR)
tier2_retriever = Tier2UserRetrieval(settings.CHROMA_PERSIST_DIR)
token_budget_manager = TokenBudgetManager()
context_builder = ContextBuilder()


@router.get("/runtime/status")
def get_runtime_status():
    """
    Returns transparency status of the currently loaded model, hardware tier,
    and routing explanation as required by Phase 05.
    """
    return runtime_manager.get_status()


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """
    Real-time Server-Sent Events (SSE) token streaming endpoint.
    Routes prompt to the appropriate model tier and streams tokens with client cancellation support.
    """
    start_time = time.time()
    
    # 1. Layer 1 Security Guard
    is_safe, block_reason, score, q_hash = input_guard.validate_with_score(request.message)
    if not is_safe and request.shield_on:
        async def block_stream():
            yield f'data: {{"error": "Blocked by Layer 1 Input Guard", "block_reason": "{block_reason}", "done": true}}\n\n'
        return StreamingResponse(block_stream(), media_type="text/event-stream")

    # 2. Retrieval & Context Assembly (including Vault evidence)
    t1_results = tier1_retriever.query(request.message)
    t2_results = tier2_retriever.query(request.session_id, request.message)

    # Vault-scoped document evidence (Spec 01 §5)
    active_vault_id = request.vault_id
    if not active_vault_id:
        try:
            from app.db.engine import get_sync_session
            from app.db.models import Conversation
            with get_sync_session() as session:
                conv = session.query(Conversation).filter_by(conversation_id=request.session_id).first()
                if conv and conv.project_vault_id:
                    active_vault_id = conv.project_vault_id
        except Exception:
            pass
    if active_vault_id:
        from app.services.ingest import ingest_service
        vault_evidence = ingest_service.query_vault(active_vault_id, request.message, top_k=3)
        t2_results.extend(vault_evidence)

    retrieved_chunks = fuse_bm25_dense(t1_results, t2_results, top_k=settings.retrieval.top_k)
    fitted_chunks, _ = token_budget_manager.fit_chunks(0, retrieved_chunks)

    # 3. Context Construction (System Prompt v4 with reasoning_effort)
    if request.shield_on:
        prompt = trusted_context.build_prompt(
            question=request.message,
            retrieved_chunks=fitted_chunks,
            reasoning_effort=request.reasoning_effort
        )
    else:
        context_data = "\n\n".join([
            f"Act: {c.get('act', 'General Law')}, Section: {c.get('section', 'General')}\nText: {c.get('text', '')}"
            for c in fitted_chunks
        ])
        prompt = f"You are a legal assistant. Context:\n{context_data}\n\nQuestion: {request.message}\nAnswer:"

    # 4. Stream Tokens with Cloud Fallback Router Support
    from app.runtime.router import fallback_router
    from app.runtime.cloud_runtime import CloudRuntime

    target_model = request.model or settings.DEFAULT_MODEL
    routing = fallback_router.route_request(target_model)

    if routing.use_cloud and routing.provider:
        cloud_rt = CloudRuntime(provider=routing.provider)
        token_stream = cloud_rt.generate_stream(prompt, model=routing.model)
        model_routed = routing.model
    else:
        token_stream = runtime_manager.generate_stream_with_routing(
            prompt=prompt,
            task_type="legal_reasoning",
            preferred_model=target_model,
            text_length=len(request.message)
        )
        model_routed = runtime_manager.get_routed_model_for_task("legal_reasoning")

    initial_stage_events = [
        {
            "type": "retrieval_started",
            "stage": "retrieving",
            "message": "Searching authoritative Indian legal corpus & vault..."
        },
        {
            "type": "retrieval_completed",
            "stage": "retrieving",
            "chunk_count": len(fitted_chunks),
            "message": f"Found {len(fitted_chunks)} relevant statutory evidence chunks"
        }
    ]

    sse_generator = stream_token_generator(
        token_stream=token_stream,
        session_id=request.session_id,
        metadata={"model_routing": model_routed},
        initial_events=initial_stage_events,
        fitted_chunks=fitted_chunks
    )

    return StreamingResponse(
        sse_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
