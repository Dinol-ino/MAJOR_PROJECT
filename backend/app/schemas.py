from pydantic import BaseModel
from typing import List, Optional

# --- /chat Endpoint Schemas ---
class ChatRequest(BaseModel):
    message: str
    session_id: str
    shield_on: bool

class CitationSource(BaseModel):
    act: str
    section: str
    text: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[CitationSource]
    blocked_by: Optional[str] = None  # None | "layer1" | "layer2" | "layer3"
    block_reason: Optional[str] = None

# --- /upload Endpoint Schemas ---
class UploadResponse(BaseModel):
    status: str  # "ok" | "rejected"
    chunks_added: int
    filename: str
    reason: Optional[str] = None

# --- /recommend Endpoint Schemas ---
class RecommendRequest(BaseModel):
    ram_gb: int
    vram_gb: int

class RecommendedModel(BaseModel):
    model: str
    pull: str

class RecommendResponse(BaseModel):
    recommended: List[RecommendedModel]

# --- /audit Endpoint Schemas ---
class AuditLogRow(BaseModel):
    ts: str
    action: str
    layer: Optional[str] = None
    hash: str
    prev_hash: str

class AuditLogResponse(BaseModel):
    rows: List[AuditLogRow]
