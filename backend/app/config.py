import os
from pydantic import BaseModel

class Settings(BaseModel):
    # Core Infrastructure
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:3b")
    OLLAMA_FALLBACK_MODEL: str = os.getenv("OLLAMA_FALLBACK_MODEL", "")
    OLLAMA_CONNECT_TIMEOUT_SECONDS: float = float(os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "30.0"))
    OLLAMA_GENERATION_TIMEOUT_SECONDS: float = float(os.getenv("OLLAMA_GENERATION_TIMEOUT_SECONDS", "180.0"))
    
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "./audit_log.db")
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    MAX_FILE_PAGES: int = int(os.getenv("MAX_FILE_PAGES", "100"))

    # Stage 5 — Hardware & Runtime
    HARDWARE_CACHE_TTL_SECONDS: int = int(os.getenv("HARDWARE_CACHE_TTL_SECONDS", "300"))
    MODELS_DIR: str = os.getenv("MODELS_DIR", "./models")
    MODEL_RUNTIME: str = os.getenv("MODEL_RUNTIME", "ollama")  # ollama | llamacpp | transformers | mock
    LLAMACPP_GPU: bool = os.getenv("LLAMACPP_GPU", "false").lower() == "true"
    LLAMACPP_MODEL_PATH: str = os.getenv("LLAMACPP_MODEL_PATH", "")

    # Stage 5 — Token Budget & Citations
    TOKEN_BUDGET_SAFETY_MARGIN: int = int(os.getenv("TOKEN_BUDGET_SAFETY_MARGIN", "256"))
    GENERATOR_MAX_OUTPUT_TOKENS: int = int(os.getenv("GENERATOR_MAX_OUTPUT_TOKENS", "1024"))
    GENERATOR_CONTEXT_TOKENS: int = int(os.getenv("GENERATOR_CONTEXT_TOKENS", "4096"))
    CITATION_TEXT_MAX_CHARS: int = int(os.getenv("CITATION_TEXT_MAX_CHARS", "500"))

    # Stage 5 — User Memory
    USER_PROFILE_CACHE_TTL: int = int(os.getenv("USER_PROFILE_CACHE_TTL", "86400"))
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "*"]

settings = Settings()
