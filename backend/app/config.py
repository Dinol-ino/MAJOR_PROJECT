import os
from pydantic import BaseModel

class Settings(BaseModel):
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:3b")
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "./audit_log.db")
    MAX_FILE_SIZE_MB: int = 10
    MAX_FILE_PAGES: int = 100

settings = Settings()
