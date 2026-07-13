from fastapi import APIRouter, HTTPException
from app.schemas import ChatRequest, ChatResponse, CitationSource

router = APIRouter(tags=["chat"])

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    # Stub implementation for Phase 0
    # In real pipeline, we'll run:
    # 1. Layer 1 Input Guard checks
    # 2. RAG Retrieval (Tier-1 and Tier-2)
    # 3. Layer 2 Trusted Context formatting
    # 4. Ollama Inference Call
    # 5. Layer 3 Output Guard validation
    # 6. Audit Logging
    
    # Simple default mock answer
    mock_sources = [
        CitationSource(
            act="IT Act",
            section="66",
            text="Section 66: Computer related offences. If any person, dishonestly or fraudulently..."
        )
    ]
    
    return ChatResponse(
        answer="This is a stub answer for Section 66 of the IT Act. The real pipeline will run in Phase 2/3.",
        sources=mock_sources,
        blocked_by=None,
        block_reason=None
    )
