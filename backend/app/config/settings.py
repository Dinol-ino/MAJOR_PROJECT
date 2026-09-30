import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env from the backend directory, then the project root.
#
# Precedence, strongest first:
#   1. real environment variables (Docker Compose `environment:`, shell exports)
#   2. backend/.env         — native-run configuration
#   3. <project root>/.env  — Compose configuration; fills gaps only
#
# load_dotenv() never overrides an already-set value, so loading backend/.env
# first is what gives it priority over the root file. Both paths are derived
# explicitly rather than via find_dotenv()'s upward walk, which resolves against
# the calling frame and so previously returned backend/.env for both calls —
# leaving the project-root file unread outside Docker.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_backend_env = os.path.join(_BACKEND_DIR, ".env")
if os.path.exists(_backend_env):
    load_dotenv(_backend_env)

_root_env = os.path.join(os.path.dirname(_BACKEND_DIR), ".env")
if os.path.exists(_root_env):
    load_dotenv(_root_env)


class ModelConfig(BaseModel):
    ollama_url: str = Field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"))
    default_model: str = Field(default_factory=lambda: os.getenv("DEFAULT_MODEL", "qwen2.5:3b"))
    fallback_model: str = Field(default_factory=lambda: os.getenv("OLLAMA_FALLBACK_MODEL", ""))
    hf_token: str = Field(default_factory=lambda: os.getenv("HF_TOKEN", ""))
    connect_timeout_seconds: float = Field(default_factory=lambda: float(os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "2.0")))
    generation_timeout_seconds: float = Field(default_factory=lambda: float(os.getenv("OLLAMA_GENERATION_TIMEOUT_SECONDS", "30.0")))
    runtime: str = Field(default_factory=lambda: os.getenv("MODEL_RUNTIME", "ollama"))  # ollama | llamacpp | transformers | mock
    llamacpp_gpu: bool = Field(default_factory=lambda: os.getenv("LLAMACPP_GPU", "false").lower() == "true")
    llamacpp_model_path: str = Field(default_factory=lambda: os.getenv("LLAMACPP_MODEL_PATH", ""))
    num_gpu_layers: int = Field(default_factory=lambda: int(os.getenv("OLLAMA_NUM_GPU_LAYERS", "-1")))  # -1=let Ollama decide, 0=CPU-only, N=layers
    context_tokens: int = Field(default_factory=lambda: int(os.getenv("GENERATOR_CONTEXT_TOKENS", "8192")))
    max_output_tokens: int = Field(default_factory=lambda: int(os.getenv("GENERATOR_MAX_OUTPUT_TOKENS", "2048")))
    models_dir: str = Field(default_factory=lambda: os.getenv("MODELS_DIR", "./models"))
    # How long Ollama keeps the model in memory after a request. Its own default is 5 minutes, so
    # a lawyer who pauses to read an answer paid the full model-load time on the next question.
    keep_alive: str = Field(default_factory=lambda: os.getenv("OLLAMA_KEEP_ALIVE", "30m"))
    routing_enabled: bool = Field(default_factory=lambda: os.getenv("MODEL_ROUTING_ENABLED", "true").lower() == "true")
    model_warmup_on_startup: bool = Field(default_factory=lambda: os.getenv("MODEL_WARMUP_ON_STARTUP", "true").lower() == "true")
    # Downloads are an explicit user action by default. Opting in via env is itself an explicit operator decision.
    auto_pull_on_startup: bool = Field(default_factory=lambda: os.getenv("AUTO_PULL_ON_STARTUP", "false").lower() == "true")
    # Never download a model in the middle of a chat request unless the operator explicitly allows it.
    auto_pull_on_demand: bool = Field(default_factory=lambda: os.getenv("AUTO_PULL_ON_DEMAND", "false").lower() == "true")
    generation_retries: int = Field(default_factory=lambda: int(os.getenv("OLLAMA_GENERATION_RETRIES", "2")))
    tags_cache_seconds: float = Field(default_factory=lambda: float(os.getenv("OLLAMA_TAGS_CACHE_SECONDS", "5")))
    probe_timeout_seconds: float = Field(default_factory=lambda: float(os.getenv("OLLAMA_PROBE_TIMEOUT_SECONDS", "3")))
    warmup_timeout_seconds: float = Field(default_factory=lambda: float(os.getenv("MODEL_WARMUP_TIMEOUT_SECONDS", "180")))
    model_idle_unload_seconds: int = Field(default_factory=lambda: int(os.getenv("MODEL_IDLE_UNLOAD_SECONDS", "600")))


def _csv_env(name: str, default: str) -> List[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


class AuthConfig(BaseModel):
    """Session/JWT authentication policy. Secrets are read from the environment only."""
    jwt_secret: str = Field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", ""))
    jwt_algorithm: str = Field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"))
    session_ttl_seconds: int = Field(default_factory=lambda: int(os.getenv("AUTH_SESSION_TTL_SECONDS", str(7 * 86400))))
    password_min_length: int = Field(default_factory=lambda: int(os.getenv("AUTH_PASSWORD_MIN_LENGTH", "8")))
    registration_open: bool = Field(default_factory=lambda: os.getenv("AUTH_REGISTRATION_OPEN", "false").lower() == "true")  # first account is always allowed; further sign-ups are opt-in
    max_failed_attempts: int = Field(default_factory=lambda: int(os.getenv("AUTH_MAX_FAILED_ATTEMPTS", "5")))
    lockout_seconds: int = Field(default_factory=lambda: int(os.getenv("AUTH_LOCKOUT_SECONDS", "900")))
    token_cache_max_entries: int = Field(default_factory=lambda: int(os.getenv("AUTH_TOKEN_CACHE_MAX_ENTRIES", "2048")))


class SecurityConfig(BaseModel):
    injection_risk_threshold: float = Field(default_factory=lambda: float(os.getenv("INJECTION_RISK_THRESHOLD", "0.7")))
    grounding_overlap_threshold: float = Field(default_factory=lambda: float(os.getenv("GROUNDING_OVERLAP_THRESHOLD", "0.05")))
    enable_pii_scanning: bool = Field(default_factory=lambda: os.getenv("ENABLE_PII_SCANNING", "true").lower() == "true")
    pii_entities: List[str] = ["PHONE_NUMBER", "EMAIL_ADDRESS", "AADHAAR_NUMBER", "PAN_NUMBER", "CREDIT_CARD", "IP_ADDRESS"]
    max_query_chars: int = 2000
    allowed_origins: List[str] = Field(default_factory=lambda: _csv_env("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,tauri://localhost"))
    # The unshielded baseline bypasses Layers 1-3 and exists only for offline security evaluation.
    allow_unshielded_baseline: bool = Field(default_factory=lambda: os.getenv("ALLOW_UNSHIELDED_BASELINE", "false").lower() == "true")
    allow_credentials: bool = Field(default_factory=lambda: os.getenv("ALLOW_CREDENTIALS", "true").lower() == "true")
    # How a broken citation contract is handled when the model returns a substantive
    # answer over real evidence but emits no parseable [^S:...] token.
    #   "warn"  - answer is returned, flagged, and its grounding score surfaced (default)
    #   "block" - answer is quarantined like any other Layer 3 failure
    # Never silently ignored: silence is what made this undetectable before.
    citation_contract_mode: str = Field(default_factory=lambda: os.getenv("CITATION_CONTRACT_MODE", "warn").lower())
    # Minimum grounding score (0-100) an answer must reach before it is flagged as weakly grounded.
    min_grounding_score: float = Field(default_factory=lambda: float(os.getenv("MIN_GROUNDING_SCORE", "50")))



# Same directory as _BACKEND_DIR above; kept under its original name for callers.
_BASE_DIR = _BACKEND_DIR

class RetrievalConfig(BaseModel):
    chroma_persist_dir: str = Field(default_factory=lambda: os.getenv("CHROMA_PERSIST_DIR", os.path.join(_BASE_DIR, "chroma_db")))
    bm25_index_dir: str = Field(default_factory=lambda: os.getenv("BM25_INDEX_DIR", os.path.join(_BASE_DIR, "bm25_index")))
    max_file_size_mb: int = Field(default_factory=lambda: int(os.getenv("MAX_FILE_SIZE_MB", "10")))
    max_file_pages: int = Field(default_factory=lambda: int(os.getenv("MAX_FILE_PAGES", "100")))
    # "truncate" ingests the first max_file_pages pages and records the truncation;
    # "reject" refuses the whole document, which is what the ingester used to do.
    # Either way the page budget is bounded, so extraction cost is unchanged.
    pdf_page_overflow_mode: str = Field(
        default_factory=lambda: (os.getenv("PDF_PAGE_OVERFLOW_MODE") or "truncate").strip().lower()
    )
    retrieval_embeddings: str = Field(default_factory=lambda: os.getenv("RETRIEVAL_EMBEDDINGS", "local"))  # local | model
    embedding_model_name: str = Field(default_factory=lambda: os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-en"))
    citation_text_max_chars: int = Field(default_factory=lambda: int(os.getenv("CITATION_TEXT_MAX_CHARS", "500")))
    rrf_k: int = 60
    top_k: int = 5
    fusion_routing_enabled: bool = Field(default_factory=lambda: os.getenv("FUSION_ROUTING_ENABLED", "true").lower() == "true")
    pageindex_routing_heuristic: bool = True
    dedup_similarity_threshold: float = 0.85
    exclude_superseded: bool = True
    # Share of a query's distinctive terms a chunk must contain to count as evidence for it.
    agentic_retrieval_enabled: bool = Field(default_factory=lambda: os.getenv("AGENTIC_RETRIEVAL_ENABLED", "false").strip().lower() in ("1", "true", "yes"))
    evidence_min_term_coverage: float = Field(default_factory=lambda: float(os.getenv("EVIDENCE_MIN_TERM_COVERAGE", "0.34")))
    # Dense-only hits (no lexical support) are kept only above this similarity. Uncalibrated
    # default: tune against your embedding model with the evaluation harness.
    vault_dense_min_score: float = Field(default_factory=lambda: float(os.getenv("VAULT_DENSE_MIN_SCORE", "0.6")))
    vault_max_files: int = Field(default_factory=lambda: int(os.getenv("VAULT_MAX_FILES", "10")))
    # Canonical home of the ORIGINAL uploaded documents. Chroma/BM25 are derived indexes
    # that can be rebuilt from these files; nothing here is ever removed by cache eviction,
    # re-indexing, a model switch or a restart - only by an explicit delete.
    vault_files_dir: str = Field(default_factory=lambda: os.getenv("VAULT_FILES_DIR", os.path.join(_BASE_DIR, "vault_files")))


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
    max_execution_time_seconds: float = Field(default_factory=lambda: float(os.getenv("MAX_EXECUTION_TIME_SECONDS", "180.0")))
    max_retrieved_docs: int = Field(default_factory=lambda: int(os.getenv("MAX_RETRIEVED_DOCS_PER_REQUEST", "15")))
    max_network_requests: int = Field(default_factory=lambda: int(os.getenv("MAX_NETWORK_REQUESTS_PER_REQUEST", "5")))
    retry_budget: int = Field(default_factory=lambda: int(os.getenv("RETRY_BUDGET", "2")))
    circuit_breaker_failure_threshold: int = Field(default_factory=lambda: int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3")))
    circuit_breaker_recovery_seconds: float = Field(default_factory=lambda: float(os.getenv("CIRCUIT_BREAKER_RECOVERY_SECONDS", "120.0")))


def _profile(level: str, **defaults) -> Dict[str, Any]:
    """Reasoning profile with per-field env overrides, e.g. REASONING_HIGH_MAX_OUTPUT_TOKENS=3072."""
    out: Dict[str, Any] = {}
    for key, default in defaults.items():
        raw = os.getenv(f"REASONING_{level.upper()}_{key.upper()}")
        out[key] = type(default)(raw) if raw not in (None, "") else default
    return out


class ReasoningConfig(BaseModel):
    """
    LOW / MEDIUM / HIGH change real resource budgets (retrieval depth, evidence volume,
    tool calls, generation length, verification retries). All values stay under the
    orchestrator hard ceilings in OrchestratorConfig.
    """
    low: Dict[str, Any] = Field(default_factory=lambda: _profile(
        "low", retrieval_top_k=3, max_evidence_chunks=4, max_tool_calls=0, max_output_tokens=512,
        retry_budget=0, context_fraction=0.5, graph_expansion=0, deep_thinking=0))
    medium: Dict[str, Any] = Field(default_factory=lambda: _profile(
        "medium", retrieval_top_k=5, max_evidence_chunks=8, max_tool_calls=2, max_output_tokens=1024,
        retry_budget=1, context_fraction=0.75, graph_expansion=1, deep_thinking=0))
    high: Dict[str, Any] = Field(default_factory=lambda: _profile(
        "high", retrieval_top_k=8, max_evidence_chunks=12, max_tool_calls=4, max_output_tokens=2048,
        retry_budget=2, context_fraction=0.9, graph_expansion=1, deep_thinking=1))

    def for_effort(self, effort: Optional[str]) -> Dict[str, Any]:
        level = (effort or "medium").lower()
        level = {"off": "low", "none": "low", "minimal": "low"}.get(level, level)
        profile = getattr(self, level, None) or self.medium
        return {"level": level if level in ("low", "medium", "high") else "medium", **profile}


class ObservabilityConfig(BaseModel):
    enabled: bool = Field(default_factory=lambda: os.getenv("OBSERVABILITY_ENABLED", "true").lower() == "true")
    retention_days: int = Field(default_factory=lambda: int(os.getenv("METRICS_RETENTION_DAYS", "30")))
    diagnostics_host: str = Field(default_factory=lambda: os.getenv("DIAGNOSTICS_HOST", "127.0.0.1"))
    enable_redaction: bool = Field(default_factory=lambda: os.getenv("OBSERVABILITY_REDACTION", "true").lower() == "true")
    max_memory_buffer_records: int = Field(default_factory=lambda: int(os.getenv("METRICS_BUFFER_SIZE", "1000")))


class CloudFallbackConfig(BaseModel):
    enabled: bool = Field(default_factory=lambda: os.getenv("CLOUD_FALLBACK_ENABLED", "false").lower() == "true")
    auto_fallback: bool = Field(default_factory=lambda: os.getenv("CLOUD_AUTO_FALLBACK", "false").lower() == "true")
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
    auth: AuthConfig = Field(default_factory=AuthConfig)
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
    reasoning: ReasoningConfig = Field(default_factory=ReasoningConfig)

    # Flat backward-compatible aliases
    @property
    def OLLAMA_URL(self) -> str:
        url = self.model.ollama_url
        if "://ollama:" in url:
            import socket
            try:
                socket.gethostbyname("ollama")
            except Exception:
                return url.replace("://ollama:", "://127.0.0.1:")
        return url

    @property
    def HF_TOKEN(self) -> str:
        return self.model.hf_token

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
    def VAULT_FILES_DIR(self) -> str:
        return self.retrieval.vault_files_dir

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
        return os.getenv("SECRET_KEY", "")


settings = Settings()
