from pydantic import BaseModel
from typing import List, Optional

# --- /chat Endpoint Schemas ---
class ChatRequest(BaseModel):
    message: str
    session_id: str
    shield_on: bool
    model: Optional[str] = None

class CitationSource(BaseModel):
    act: str
    section: str
    text: str
    similarity_score: Optional[float] = None
    trust_score: Optional[float] = None
    freshness_score: Optional[float] = None
    injection_risk_score: Optional[float] = None
    confidence_score: Optional[float] = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[CitationSource]
    blocked_by: Optional[str] = None  # None | "layer1" | "layer1.5" | "layer2" | "layer3"
    block_reason: Optional[str] = None
    confidence_score: Optional[float] = None
    hallucination_flags: Optional[List[str]] = None

# --- /upload Endpoint Schemas ---
class UploadResponse(BaseModel):
    status: str  # "ok" | "rejected"
    chunks_added: int
    filename: str
    reason: Optional[str] = None

# --- /recommend Endpoint Schemas ---
class RecommendRequest(BaseModel):
    ram_gb: Optional[float] = None
    vram_gb: Optional[float] = None

class RecommendedModel(BaseModel):
    model_id: str
    display_name: str
    provider: str
    size_gb: float
    ram_required_gb: float
    context_window: int
    tier: str
    ollama_tag: Optional[str] = None

class RecommendResponse(BaseModel):
    recommended: List[RecommendedModel]
    detected_hardware: Optional[dict] = None

# --- /audit Endpoint Schemas ---
class AuditLogRow(BaseModel):
    ts: str
    action: str
    layer: Optional[str] = None
    hash: str
    prev_hash: str

class AuditLogResponse(BaseModel):
    rows: List[AuditLogRow]
