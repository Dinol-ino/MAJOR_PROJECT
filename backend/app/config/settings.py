import os
from typing import List, Optional
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    ollama_url: str = Field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"))
    default_model: str = Field(default_factory=lambda: os.getenv("DEFAULT_MODEL", "gemma2:2b"))
    fallback_model: str = Field(default_factory=lambda: os.getenv("OLLAMA_FALLBACK_MODEL", "qwen2.5:3b"))
    connect_timeout_seconds: float = Field(default_factory=lambda: float(os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "30.0")))
    generation_timeout_seconds: float = Field(default_factory=lambda: float(os.getenv("OLLAMA_GENERATION_TIMEOUT_SECONDS", "180.0")))
    runtime: str = Field(default_factory=lambda: os.getenv("MODEL_RUNTIME", "ollama"))  # ollama | llamacpp | transformers | mock
    llamacpp_gpu: bool = Field(default_factory=lambda: os.getenv("LLAMACPP_GPU", "false").lower() == "true")
    llamacpp_model_path: str = Field(default_factory=lambda: os.getenv("LLAMACPP_MODEL_PATH", ""))
    num_gpu_layers: int = Field(default_factory=lambda: int(os.getenv("OLLAMA_NUM_GPU_LAYERS", "0")))  # -1=auto, 0=CPU-only
    context_tokens: int = Field(default_factory=lambda: int(os.getenv("GENERATOR_CONTEXT_TOKENS", "4096")))
    max_output_tokens: int = Field(default_factory=lambda: int(os.getenv("GENERATOR_MAX_OUTPUT_TOKENS", "1024")))
    models_dir: str = Field(default_factory=lambda: os.getenv("MODELS_DIR", "./models"))
    routing_enabled: bool = Field(default_factory=lambda: os.getenv("MODEL_ROUTING_ENABLED", "true").lower() == "true")
    model_warmup_on_startup: bool = Field(default_factory=lambda: os.getenv("MODEL_WARMUP_ON_STARTUP", "true").lower() == "true")
    model_idle_unload_seconds: int = Field(default_factory=lambda: int(os.getenv("MODEL_IDLE_UNLOAD_SECONDS", "600")))


class SecurityConfig(BaseModel):
    injection_risk_threshold: float = Field(default_factory=lambda: float(os.getenv("INJECTION_RISK_THRESHOLD", "0.7")))
    grounding_overlap_threshold: float = Field(default_factory=lambda: float(os.getenv("GROUNDING_OVERLAP_THRESHOLD", "0.05")))
    enable_pii_scanning: bool = Field(default_factory=lambda: os.getenv("ENABLE_PII_SCANNING", "true").lower() == "true")
    pii_entities: List[str] = ["PHONE_NUMBER", "EMAIL_ADDRESS", "AADHAAR_NUMBER", "PAN_NUMBER", "CREDIT_CARD", "IP_ADDRESS"]
    max_query_chars: int = 2000
    allowed_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "tauri://localhost"]



_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class RetrievalConfig(BaseModel):
    chroma_persist_dir: str = Field(default_factory=lambda: os.getenv("CHROMA_PERSIST_DIR", os.path.join(_BASE_DIR, "chroma_db")))
    bm25_index_dir: str = Field(default_factory=lambda: os.getenv("BM25_INDEX_DIR", os.path.join(_BASE_DIR, "bm25_index")))
    max_file_size_mb: int = Field(default_factory=lambda: int(os.getenv("MAX_FILE_SIZE_MB", "10")))
    max_file_pages: int = Field(default_factory=lambda: int(os.getenv("MAX_FILE_PAGES", "100")))
    retrieval_embeddings: str = Field(default_factory=lambda: os.getenv("RETRIEVAL_EMBEDDINGS", "local"))  # local | model
    embedding_model_name: str = Field(default_factory=lambda: os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-en"))
    citation_text_max_chars: int = Field(default_factory=lambda: int(os.getenv("CITATION_TEXT_MAX_CHARS", "500")))
    rrf_k: int = 60
    top_k: int = 5
    fusion_routing_enabled: bool = Field(default_factory=lambda: os.getenv("FUSION_ROUTING_ENABLED", "true").lower() == "true")
    pageindex_routing_heuristic: bool = True
    dedup_similarity_threshold: float = 0.85
    exclude_superseded: bool = True
    vault_max_files: int = Field(default_factory=lambda: int(os.getenv("VAULT_MAX_FILES", "10")))


class MemoryConfig(BaseModel):
    sqlite_db_path: str = Field(default_factory=lambda: os.getenv("SQLITE_DB_PATH", "./audit_log.db"))
    transcript_db_path: str = Field(default_factory=lambda: os.getenv("TRANSCRIPT_DB_PATH", "./transcript_memory.db"))
    postgres_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    redis_url: str = Field(default_factory=lambda: os.getenv("REDIS_URL", ""))

    session_ttl_seconds: int = Field(default_factory=lambda: int(os.getenv("SESSION_TTL_SECONDS", "7200")))
    user_profile_cache_ttl: int = Field(default_factory=lambda: int(os.getenv("USER_PROFILE_CACHE_TTL", "86400")))
    l2_conversation_retention_days: int = Field(default_factory=lambda: int(os.getenv("L2_CONVERSATION_RETENTION_DAYS", "90")))
    l3_semantic_dedup_threshold: float = Field(default_factory=lambda: float(os.getenv("L3_SEMANTIC_DEDUP_THRESHOLD", "0.85")))
    l4_document_max_age_days: int = Field(default_factory=lambda: int(os.getenv("L4_DOCUMENT_MAX_AGE_DAYS", "365")))
    l5_research_retention_days: int = Field(default_factory=lambda: int(os.getenv("L5_RESEARCH_RETENTION_DAYS", "180")))
    l6_audit_retention_days: int = Field(default_factory=lambda: int(os.getenv("L6_AUDIT_RETENTION_DAYS", "730")))


class MCPConfig(BaseModel):
    permissions_config_path: str = os.path.join(os.path.dirname(__file__), "mcp_permissions.yaml")
    enabled_servers: List[str] = ["local-statute-server", "indian-legal-gateway"]
    timeout_seconds: float = 30.0


class PerformanceConfig(BaseModel):
    hardware_cache_ttl_seconds: int = Field(default_factory=lambda: int(os.getenv("HARDWARE_CACHE_TTL_SECONDS", "300")))
    token_budget_safety_margin: int = Field(default_factory=lambda: int(os.getenv("TOKEN_BUDGET_SAFETY_MARGIN", "256")))
    cache_enabled: bool = Field(default_factory=lambda: os.getenv("CACHE_ENABLED", "true").lower() == "true")
    l1_cache_max_size: int = Field(default_factory=lambda: int(os.getenv("L1_CACHE_MAX_SIZE", "500")))
    l1_cache_ttl_seconds: int = Field(default_factory=lambda: int(os.getenv("L1_CACHE_TTL_SECONDS", "60")))
    l2_retrieval_cache_max_size: int = Field(default_factory=lambda: int(os.getenv("L2_RETRIEVAL_CACHE_MAX_SIZE", "1000")))
    l2_retrieval_cache_ttl_seconds: int = Field(default_factory=lambda: int(os.getenv("L2_RETRIEVAL_CACHE_TTL_SECONDS", "3600")))
    l3_embedding_cache_max_size: int = Field(default_factory=lambda: int(os.getenv("L3_EMBEDDING_CACHE_MAX_SIZE", "5000")))
    l3_embedding_cache_ttl_seconds: int = Field(default_factory=lambda: int(os.getenv("L3_EMBEDDING_CACHE_TTL_SECONDS", "86400")))
    corpus_version_hash: str = Field(default_factory=lambda: os.getenv("CORPUS_VERSION_HASH", "v1.0.0_statutes_2026"))


class NetworkModeConfig(BaseModel):
    default_mode: str = "OFFLINE"  # OFFLINE | ONLINE
    legal_sources_path: str = os.path.join(os.path.dirname(__file__), "legal_sources.yaml")


class OrchestratorConfig(BaseModel):
    enabled: bool = Field(default_factory=lambda: os.getenv("ORCHESTRATOR_ENABLED", "true").lower() == "true")
    max_steps: int = Field(default_factory=lambda: int(os.getenv("MAX_STEPS_PER_REQUEST", "8")))
    max_tool_calls: int = Field(default_factory=lambda: int(os.getenv("MAX_TOOL_CALLS_PER_REQUEST", "5")))
    max_tokens: int = Field(default_factory=lambda: int(os.getenv("MAX_TOKENS_PER_REQUEST", "8192")))
    max_execution_time_seconds: float = Field(default_factory=lambda: float(os.getenv("MAX_EXECUTION_TIME_SECONDS", "60.0")))
    max_retrieved_docs: int = Field(default_factory=lambda: int(os.getenv("MAX_RETRIEVED_DOCS_PER_REQUEST", "15")))
    max_network_requests: int = Field(default_factory=lambda: int(os.getenv("MAX_NETWORK_REQUESTS_PER_REQUEST", "5")))
    retry_budget: int = Field(default_factory=lambda: int(os.getenv("RETRY_BUDGET", "2")))
    circuit_breaker_failure_threshold: int = Field(default_factory=lambda: int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3")))
    circuit_breaker_recovery_seconds: float = Field(default_factory=lambda: float(os.getenv("CIRCUIT_BREAKER_RECOVERY_SECONDS", "120.0")))


class ObservabilityConfig(BaseModel):
    enabled: bool = Field(default_factory=lambda: os.getenv("OBSERVABILITY_ENABLED", "true").lower() == "true")
    retention_days: int = Field(default_factory=lambda: int(os.getenv("METRICS_RETENTION_DAYS", "30")))
    diagnostics_host: str = Field(default_factory=lambda: os.getenv("DIAGNOSTICS_HOST", "127.0.0.1"))
    enable_redaction: bool = Field(default_factory=lambda: os.getenv("OBSERVABILITY_REDACTION", "true").lower() == "true")
    max_memory_buffer_records: int = Field(default_factory=lambda: int(os.getenv("METRICS_BUFFER_SIZE", "1000")))


class CloudFallbackConfig(BaseModel):
    enabled: bool = Field(default_factory=lambda: os.getenv("CLOUD_FALLBACK_ENABLED", "true").lower() == "true")
    auto_fallback: bool = Field(default_factory=lambda: os.getenv("CLOUD_AUTO_FALLBACK", "true").lower() == "true")
    active_provider: str = Field(default_factory=lambda: os.getenv("CLOUD_PROVIDER", "grok").lower())  # grok | zai
    grok_api_base: str = Field(default_factory=lambda: os.getenv("GROK_API_BASE", "https://api.x.ai/v1"))
    grok_model: str = Field(default_factory=lambda: os.getenv("GROK_MODEL", "grok-2"))
    zai_api_base: str = Field(default_factory=lambda: os.getenv("ZAI_API_BASE", "https://api.z.ai/v1"))
    zai_model: str = Field(default_factory=lambda: os.getenv("ZAI_MODEL", "z.ai-chat"))


class GraphConfig(BaseModel):
    backend: str = Field(default_factory=lambda: os.getenv("GRAPH_BACKEND", "auto"))  # auto | memgraph | in_process
    memgraph_uri: str = Field(default_factory=lambda: os.getenv("MEMGRAPH_URI", "bolt://127.0.0.1:7687"))
    memgraph_user: str = Field(default_factory=lambda: os.getenv("MEMGRAPH_USER", ""))
    memgraph_password: str = Field(default_factory=lambda: os.getenv("MEMGRAPH_PASSWORD", ""))
    cypher_timeout_seconds: float = Field(default_factory=lambda: float(os.getenv("CYPHER_TIMEOUT_SECONDS", "5.0")))


class Settings(BaseModel):
    """
    Centralized, typed configuration registry for DFrag.
    Provides structured concern objects and flat backward-compatible property accessors.
    """
    model: ModelConfig = Field(default_factory=ModelConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    network: NetworkModeConfig = Field(default_factory=NetworkModeConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    cloud_fallback: CloudFallbackConfig = Field(default_factory=CloudFallbackConfig)
    graph: GraphConfig = Field(default_factory=GraphConfig)

    # Flat backward-compatible aliases
    @property
    def OLLAMA_URL(self) -> str:
        return self.model.ollama_url

    @property
    def DEFAULT_MODEL(self) -> str:
        return self.model.default_model

    @DEFAULT_MODEL.setter
    def DEFAULT_MODEL(self, value: str):
        self.model.default_model = value

    @property
    def OLLAMA_FALLBACK_MODEL(self) -> str:
        return self.model.fallback_model

    @property
    def OLLAMA_CONNECT_TIMEOUT_SECONDS(self) -> float:
        return self.model.connect_timeout_seconds

    @property
    def OLLAMA_GENERATION_TIMEOUT_SECONDS(self) -> float:
        return self.model.generation_timeout_seconds

    @property
    def MODEL_RUNTIME(self) -> str:
        return self.model.runtime

    @MODEL_RUNTIME.setter
    def MODEL_RUNTIME(self, value: str):
        self.model.runtime = value

    @property
    def LLAMACPP_GPU(self) -> bool:
        return self.model.llamacpp_gpu

    @property
    def LLAMACPP_MODEL_PATH(self) -> str:
        return self.model.llamacpp_model_path

    @property
    def OLLAMA_NUM_GPU_LAYERS(self) -> int:
        return self.model.num_gpu_layers

    @property
    def GENERATOR_CONTEXT_TOKENS(self) -> int:
        return self.model.context_tokens

    @property
    def GENERATOR_MAX_OUTPUT_TOKENS(self) -> int:
        return self.model.max_output_tokens

    @property
    def MODELS_DIR(self) -> str:
        return self.model.models_dir

    @property
    def CHROMA_PERSIST_DIR(self) -> str:
        return self.retrieval.chroma_persist_dir

    @property
    def SQLITE_DB_PATH(self) -> str:
        return self.memory.sqlite_db_path

    @property
    def TRANSCRIPT_DB_PATH(self) -> str:
        return self.memory.transcript_db_path

    @property
    def MAX_FILE_SIZE_MB(self) -> int:
        return self.retrieval.max_file_size_mb

    @property
    def MAX_FILE_PAGES(self) -> int:
        return self.retrieval.max_file_pages

    @property
    def HARDWARE_CACHE_TTL_SECONDS(self) -> int:
        return self.performance.hardware_cache_ttl_seconds

    @property
    def TOKEN_BUDGET_SAFETY_MARGIN(self) -> int:
        return self.performance.token_budget_safety_margin

    @property
    def CITATION_TEXT_MAX_CHARS(self) -> int:
        return self.retrieval.citation_text_max_chars

    @property
    def INJECTION_RISK_THRESHOLD(self) -> float:
        return self.security.injection_risk_threshold

    @property
    def GROUNDING_OVERLAP_THRESHOLD(self) -> float:
        return self.security.grounding_overlap_threshold

    @property
    def ENABLE_PII_SCANNING(self) -> bool:
        return self.security.enable_pii_scanning

    @property
    def USER_PROFILE_CACHE_TTL(self) -> int:
        return self.memory.user_profile_cache_ttl

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        return self.security.allowed_origins

    @property
    def network_mode(self) -> NetworkModeConfig:
        return self.network

    @property
    def SECRET_KEY(self) -> str:
        return os.getenv("SECRET_KEY", "dfrag-vault-default-secret-key-32bytes-min!")


settings = Settings()
