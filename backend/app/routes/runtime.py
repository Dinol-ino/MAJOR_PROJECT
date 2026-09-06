import time
import logging
from typing import Optional
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas import ChatRequest
from app.runtime import runtime_manager, stream_token_generator
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

    # 2. Retrieval & Context Assembly
    t1_results = tier1_retriever.query(request.message)
    t2_results = tier2_retriever.query(request.session_id, request.message)
    retrieved_chunks = fuse_bm25_dense(t1_results, t2_results, top_k=settings.retrieval.top_k)

    fitted_chunks, _ = token_budget_manager.fit_chunks(0, retrieved_chunks)

    # 3. Context Construction
    if request.shield_on:
        anonymized_query = trusted_context.anonymize(request.message)
        prompt = context_builder.build_defensive_prompt(
            user_query=anonymized_query,
            retrieved_chunks=fitted_chunks,
            conversation_history=[]
        )
    else:
        context_data = "\n\n".join([
            f"Act: {c.get('act', 'General Law')}, Section: {c.get('section', 'General')}\nText: {c.get('text', '')}"
            for c in fitted_chunks
        ])
        prompt = f"You are a legal assistant. Context:\n{context_data}\n\nQuestion: {request.message}\nAnswer:"

    # 4. Stream Tokens via Model Lifecycle Manager
    token_stream = runtime_manager.generate_stream_with_routing(
        prompt=prompt,
        task_type="legal_reasoning",
        preferred_model=request.model if request.model else None,
        text_length=len(request.message)
    )

    sse_generator = stream_token_generator(
        token_stream=token_stream,
        session_id=request.session_id,
        metadata={"model_routing": runtime_manager.get_routed_model_for_task("legal_reasoning")}
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
