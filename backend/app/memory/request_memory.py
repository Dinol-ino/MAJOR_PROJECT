import time
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class RequestMemory:
    """
    Layer 1 (L1) Request Memory:
    In-process, request-scoped memory container.
    Tracks query parameters, prompt parts, transient tool outputs, token usage, and latency.
    Discarded automatically when the HTTP response is completed.
    """
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "default_user"
    session_id: str = "default_session"
    raw_query: str = ""
    sanitized_query: str = ""
    start_time: float = field(default_factory=time.perf_counter)
    
    # Transient state during pipeline execution
    retrieved_chunks: List[Dict[str, Any]] = field(default_factory=list)
    defense_signals: Dict[str, Any] = field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model_name: str = ""
    latency_ms: float = 0.0

    def mark_completed(self) -> float:
        self.latency_ms = round((time.perf_counter() - self.start_time) * 1000, 2)
        return self.latency_ms

    def record_defense_event(self, layer: str, passed: bool, details: Optional[Dict[str, Any]] = None):
        self.defense_signals[layer] = {
            "passed": passed,
            "details": details or {},
            "timestamp": time.time(),
        }

    def record_tool_call(self, server: str, tool_name: str, input_args: Dict[str, Any], result: Any):
        self.tool_calls.append({
            "server": server,
            "tool": tool_name,
            "args": input_args,
            "result_preview": str(result)[:300],
            "timestamp": time.time(),
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "raw_query": self.raw_query,
            "model_name": self.model_name,
            "latency_ms": self.latency_ms,
            "retrieved_chunk_count": len(self.retrieved_chunks),
            "defense_signals": self.defense_signals,
            "tool_call_count": len(self.tool_calls),
            "tokens": {
                "prompt": self.prompt_tokens,
                "completion": self.completion_tokens,
                "total": self.prompt_tokens + self.completion_tokens,
            },
        }


# Alias for backward compatibility
RequestMemoryContainer = RequestMemory
