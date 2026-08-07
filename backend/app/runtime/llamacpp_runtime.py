import logging
from typing import Optional, AsyncIterator

logger = logging.getLogger(__name__)

class LlamaCppRuntime:
    def __init__(self, model_path: str = ""):
        self.model_path = model_path
        self._available = False
        self._llm = None
        
        if model_path:
            try:
                from llama_cpp import Llama
                self._llm = Llama(
                    model_path=model_path,
                    n_ctx=4096,
                    verbose=False
                )
                self._available = True
                logger.info(f"Loaded llama.cpp model from {model_path}")
            except Exception as e:
                logger.warning(f"Failed to initialize llama.cpp with model {model_path}: {e}")

    async def generate(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        if not self._available or not self._llm:
            raise RuntimeError("llama.cpp runtime is not properly initialized or model file is missing.")
        res = self._llm(prompt, max_tokens=1024)
        return res["choices"][0]["text"].strip()

    async def generate_stream(self, prompt: str, model: Optional[str] = None, **kwargs) -> AsyncIterator[str]:
        if not self._available or not self._llm:
            raise RuntimeError("llama.cpp runtime is not properly initialized or model file is missing.")
        for chunk in self._llm(prompt, max_tokens=1024, stream=True):
            token = chunk["choices"][0]["text"]
            if token:
                yield token

    async def health_check(self) -> bool:
        return self._available
