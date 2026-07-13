from fastapi import APIRouter, HTTPException
from app.schemas import ChatRequest, ChatResponse, CitationSource
from app.config import settings
from app.defense.layer1_input_guard import Layer1InputGuard
from app.defense.layer2_trusted_context import Layer2TrustedContext
from app.defense.layer3_output_guard import Layer3OutputGuard
from app.defense.audit_log import AuditLogger
from app.model.ollama_client import OllamaClient
from app.retrieval.tier1_law import Tier1LawRetrieval
from app.retrieval.tier2_user import Tier2UserRetrieval
from app.retrieval.hybrid_rank import fuse_bm25_dense

router = APIRouter(tags=["chat"])

# Instantiate controllers
input_guard = Layer1InputGuard()
trusted_context = Layer2TrustedContext()
output_guard = Layer3OutputGuard()
audit_logger = AuditLogger(settings.SQLITE_DB_PATH)
ollama_client = OllamaClient(settings.OLLAMA_URL, settings.DEFAULT_MODEL)

# Retrievers (stubs for now, Sweedan will update logic inside them)
tier1_retriever = Tier1LawRetrieval(settings.CHROMA_PERSIST_DIR)
tier2_retriever = Tier2UserRetrieval(settings.CHROMA_PERSIST_DIR)

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    # 1. Retrieve raw chunks (combining Tier-1 Law DB and Tier-2 User PDF DB)
    # Stub collections query
    t1_results = tier1_retriever.query(request.message)
    t2_results = tier2_retriever.query(request.session_id, request.message)
    
    # Run Reciprocal Rank Fusion BM25 + dense ranking logic
    retrieved_chunks = fuse_bm25_dense(t1_results, t2_results, top_k=3)
    
    # Map to citation sources format
    sources = [
        CitationSource(act=c["act"], section=c["section"], text=c["text"])
        for c in retrieved_chunks
    ]

    # --- SHIELD ON PIPELINE ---
    if request.shield_on:
        # Layer 1: Input Guard Validation
        is_clean, reason = input_guard.validate(request.message)
        if not is_clean:
            # Log block event in hash-chained SQLite db
            audit_logger.log(action="chat_blocked_input", layer="layer1")
            return ChatResponse(
                answer=f"Request Blocked: {reason}",
                sources=[],
                blocked_by="layer1",
                block_reason=reason
            )
            
        # Layer 2: Build Secure System Prompt (strips embedded jailbreaks)
        prompt = trusted_context.build_prompt(request.message, retrieved_chunks)
        
        # Invoke local Ollama Runtime model
        try:
            llm_answer = await ollama_client.generate(prompt)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Ollama server error: {str(exc)}")
            
        # Layer 3: Output Guard Validation (grounding token check + system leak scan)
        is_valid, error_reason = output_guard.validate(llm_answer, retrieved_chunks, prompt)
        if not is_valid:
            audit_logger.log(action="chat_blocked_output", layer="layer3")
            return ChatResponse(
                answer=f"Response quarantined: {error_reason}",
                sources=sources,
                blocked_by="layer3",
                block_reason=error_reason
            )
            
        # Success Audit Log
        audit_logger.log(action="chat_success", layer=None)
        return ChatResponse(
            answer=llm_answer,
            sources=sources,
            blocked_by=None,
            block_reason=None
        )

    # --- SHIELD OFF PIPELINE (Bare Model / vulnerable path) ---
    else:
        # Construct plain system context (no tags wrapping, no rules, no sanitization)
        context_data = "\n\n".join([
            f"Act: {c['act']}, Section: {c['section']}\nText: {c['text']}" 
            for c in retrieved_chunks
        ])
        prompt = (
            f"You are a legal assistant. Answer the user's question using the provided context.\n\n"
            f"Context:\n{context_data}\n\n"
            f"Question: {request.message}\n"
            f"Answer:"
        )
        
        try:
            llm_answer = await ollama_client.generate(prompt)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Ollama server error: {str(exc)}")
            
        # Bypasses Layer 3 completely. Logs success but notes no shield.
        audit_logger.log(action="chat_success_shield_off", layer=None)
        return ChatResponse(
            answer=llm_answer,
            sources=sources,
            blocked_by=None,
            block_reason=None
        )
