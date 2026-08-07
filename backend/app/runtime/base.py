from typing import Protocol, Optional, AsyncIterator

class LLMRuntime(Protocol):
    """
    Standard interface for all LLM inference engines (Ollama, llama.cpp, Transformers, Mock).
    """
    async def generate(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """Generate complete text response."""
        ...

    async def generate_stream(self, prompt: str, model: Optional[str] = None, **kwargs) -> AsyncIterator[str]:
        """Stream generated tokens incrementally."""
        ...

    async def health_check(self) -> bool:
        """Verify engine availability."""
        ...
