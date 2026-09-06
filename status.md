# DFrag — Phase Execution Status

**Last Updated**: 2026-08-27  
**Operating Standard**: Strict adherence to `project/.skills/` (00-04) — No fake completeness, verify before claiming.

---

## Phase Checklist & Roadmap

| Phase | Phase Name | Status | Evidence / Validation |
| :--- | :--- | :--- | :--- |
| **01** | **Foundation & Configuration Centralization** | [x] **COMPLETE** | `backend/app/config/` package created with typed `Settings` (`ModelConfig`, `SecurityConfig`, `RetrievalConfig`, `MemoryConfig`, `MCPConfig`, `PerformanceConfig`, `NetworkModeConfig`). YAML registries (`model_registry.yaml`, `mcp_permissions.yaml`, `legal_sources.yaml`) and versioned prompts (`backend/app/prompts/` with `security_core.md` immutability) created. Defensive controllers and runtime managers default directly to centralized settings. `pytest.ini` configured for direct discovery. **10/10 tests passed** (`tests/config/`). |
| **02** | **Persistence & PostgreSQL Cutover** | [x] **COMPLETE** | Async & sync SQLAlchemy engines (`backend/app/db/engine.py`) with connection pooling, declarative ORM models (`Conversation`, `Message`, `SemanticMemory`, `DocumentMemory`, `ResearchSession`, `ResearchSource`, `AuditEvent`), `/health/db` endpoint, unified `DurableMemoryManager` & `AuditLogger` ORM cutover, document metadata persistence, and non-destructive SQLite fallback for local development. **11/11 tests passed** (`tests/test_db_persistence.py`, `tests/test_stage3_memory.py`). |
| **03** | **Layered Memory Architecture** | [x] **COMPLETE** | 6 explicit memory layers implemented: L1 Request (`request_memory.py`), L2 Conversation (`conversation_memory.py`), L3 Semantic with strict Validation Gate (`semantic_memory.py`), L4 Document with PostgreSQL+ChromaDB cascading delete (`document_memory.py`), L5 Research sessions & provenance (`research_memory.py`), L6 Immutable append-only audit ledger (`audit_memory.py`). Shared policies in `policies.py` and REST endpoints in `app/routes/memory.py`. **12/12 tests passed** (`tests/memory/`). |
| **04** | **Performance & Intelligent Caching** | [x] **COMPLETE** | In-process bounded LRU caching package (`backend/app/cache/`): L1 Process Request Cache (`l1_process_cache.py`), L2 Retrieval Cache (`l2_retrieval_cache.py`) with corpus version invalidation, L3 Embedding Vector Cache (`l3_embedding_cache.py`). L4 (model/prompt) and L5 (full response) explicitly rejected to prevent stale legal answers. Zero cross-user/cross-session cache leakage enforced. `GET /cache/metrics` endpoint mounted. **8/8 tests passed** (`tests/cache/`). |
| **05** | **LLM Runtime & Model Routing** | [x] **COMPLETE** | Config-driven Model Router (`backend/app/runtime/router.py`) mapping tasks (intent, summarization, legal reasoning) to model tiers from `model_registry.yaml` with zero hardcoded model names. `ModelLifecycleManager` (`manager.py`) with Tier 0 floor model startup warmup, automatic OOM recovery with tier stepdown & L6 audit logging, SSE token streaming generator (`streaming.py`) with client cancellation handling, lazy Chroma embedding initialization, and `GET /runtime/status` endpoint. **10/10 tests passed** (`tests/runtime/`). |
| **06** | **Retrieval Optimization & Hybrid RAG** | [x] **COMPLETE** | Persistent BM25 index (`backend/app/retrieval/bm25_index.py`) replacing per-query rebuilds with zero overhead, `FusionRouter` (`fusion_router.py`) classifying queries to route between PageIndex structural navigation (Act -> Chapter -> Section), Hybrid (Dense + BM25 + RRF), and Both. Automatic near-identical chunk deduplication (`deduplicate_chunks`), superseded provision filtering (`exclude_superseded`), singleton ChromaDB client (`client.py`), and retrieval accuracy metric suite (`metrics.py`) computing Recall@K, Precision@K, MRR, nDCG, and Citation Hit Rate. **19/19 tests passed** (`tests/retrieval/`). Full regression: **86/86 passed**. |
| **07** | **Defensive Security Upgrade** | [x] **COMPLETE** | Non-additive hard-gate validator (`backend/app/security/injection_gate.py`) rejecting prompt injections, SQLi, command injection, and path traversal with request-scoped query hash caching. Multi-source sanitizer (`context_sanitizer.py`) stripping embedded instructions and script tags. Ingestion PDF security validator (`pdf_sanitizer.py`) verifying magic bytes, page/size quotas, and active objects. Unconditional PII scanner (`pii_scanner.py`) with Presidio and deterministic regex fallback for Indian PII (Aadhaar, PAN, phone, email). Layer 3 guardrails validator (`output_validator.py`) enforcing structured schema, deterministic token overlap grounding, citation existence checking against corpus metadata, system leak blocking, and defense-in-depth PII redaction. Cryptographic SHA-256 hash-chaining verification engine (`audit_ledger.py`) with `GET /audit/verify` endpoint. **22/22 tests passed** (`tests/security/`). Full regression: **108/108 passed**. |
| **08** | **MCP Gateway & Tools Integration** | [x] **COMPLETE** | Policy-gated, schema-validated MCP Gateway (`backend/app/mcp/`) with formal tool categories (`LEGAL_SEARCH`, `CURRENT_LAW`, `CASE_LAW_SEARCH`, `GOVERNMENT_SOURCE`, `DOCUMENT_SEARCH`, `LOCAL_RETRIEVAL`, `DEEP_RESEARCH`). Policy Engine (`policy_engine.py`) enforcing allowlists, per-request call budgets, and offline-mode network blocking. Permission Layer (`permission_layer.py`) enforcing Pydantic input/output schemas. Gateway (`gateway.py`) with per-call timeouts, output sanitization (stripping instructions/scripts), `mcp_tool_calls` DB persistence, and L6 audit logging. Mounted `GET /mcp/status`, `POST /mcp/tool-call`, `GET /mcp/history` endpoints and connected dynamic React UI (`McpToolsView.jsx`). **15/15 tests passed** (`tests/mcp/`). Full regression: **123/123 passed**. |
| **09** | **Agentic Research Orchestrator** | [x] **COMPLETE** | Bounded Finite State Machine (`backend/app/orchestrator/state_machine.py`) with strictly code-controlled transitions (`INITIALIZED` -> `CLASSIFY` -> `SECURITY_CHECK` -> `PLAN` -> `RETRIEVE` -> `TOOL_CALL` -> `EVIDENCE_VALIDATION` -> `SYNTHESIS` -> `LEGAL_VERIFICATION` -> `COMPLETED`). Hard execution ceiling enforcement (`limits.py`: max steps, tool calls, tokens, execution time, docs, network requests, retries). Step-type circuit breaker (`circuit_breaker.py`) with automatic degraded fallback to local retrieval. Request cancellation manager (`cancellation.py`) with L5 session status synchronization. API endpoints mounted (`POST /research/cancel/{id}`, `POST /research/query`, `GET /research/circuit-breaker/status`). Zero shell/filesystem/eval access by architectural construction. **20/20 tests passed** (`tests/orchestrator/`). Full regression: **143/143 passed**. |
| **10** | **Online/Offline Legal Research Engine** | [x] **COMPLETE** | Hard network policy boundary (`backend/app/network/mode_enforcer.py`) with OFFLINE zero-network isolation and ONLINE domain allowlist (`legal_sources.yaml`) with SSRF protection. Mandatory 13-field cryptographic Provenance Schema (`app/research/provenance.py`). Freshness Detection Engine (`freshness.py`) with keyword heuristics and corpus metadata staleness checks. Legal Conflict Detector (`conflict_detector.py`) surfacing statutory supersessions and amendments without silent overwrites. 10-Step Bounded Research Pipeline (`pipeline.py`). Mounted `GET /research/mode`, `POST /research/mode`, and `POST /research/pipeline`. **18/18 tests passed** (`tests/network/`, `tests/research/`). Full regression: **161/161 passed**. |
| **11** | **Observability & Benchmarking** | [x] **COMPLETE** | Request Correlation Tracking (`backend/app/observability/correlation.py`) propagating `X-Correlation-ID`. Confidentiality Redactor (`redaction.py`) preventing raw prompt/document leakage into logs/metrics while tracking structural tokens and SHA-256 hashes. In-Process Metrics Collector (`metrics.py`) with ring buffer + `request_metrics` DB persistence. Diagnostics dashboard (`GET /diagnostics`, `/diagnostics/trace/{id}`, `/diagnostics/metrics/summary`). Automated benchmark runner (`benchmark.py`) generating empirical `PERFORMANCE_BUDGETS.md`. **11/11 tests passed** (`tests/observability/`). Full regression: **172/172 passed**. |
| **12** | **Evaluation & Adversarial Attack Testing** | [x] **COMPLETE** | Extended 110-vector adversarial suite (`attacks.json`), 25-case legal benchmark dataset (`legal_benchmark_dataset.json`), SQLite-backed eval run store (`run_store.py`), zero-bypass security suite (`security_suite.py`), memory isolation suite (`memory_suite.py`), MCP offline policy suite (`mcp_suite.py`), legal accuracy suite (`legal_accuracy_suite.py`), and non-vacuous mutation checker (`mutation_check.py`). Surfaced & hardened 46 injection gate gaps and 11 context sanitizer indirect injection gaps. **18/18 eval tests passed**, **190/190 full backend regression tests passed**. |
| **13** | **Playwright E2E Testing** | [x] **COMPLETE** | Playwright E2E browser testing suite (`frontend/playwright.config.ts`, `frontend/e2e/`). Confirmed zero Playwright runtime path usage (dev dependency only). 7 comprehensive test specs covering: chat streaming & token generation, single & batch PDF document upload and non-PDF validation, citation rendering with section badges & trust scores, 3-layer defensive shield ON/OFF toggle & explicit security refusal banner, MCP Gateway navigation with OFFLINE/ONLINE network mode badge & REST catalog, backend 500 error handling resilience, and keyboard navigation accessibility. **13/13 E2E tests passed (12.6s)**. |
| **14** | **Frontend Performance & Consensus UX** | [x] **COMPLETE** | 7-principle Consensus UX audit completed. Implemented permanent `ModeIndicator` (Phase 10 OFFLINE/ONLINE requirement) mounted in `ManusHeader.jsx`, progressive disclosure `ProvenancePanel` (Phase 10 13-field provenance schema with expandable accordion displaying Jurisdiction, Version, Publication Date, Superseded/Active status, and SHA-256 Content Hash), and transparent `ConfidenceIndicator` grounding breakdown. Production build clean (`npm run build` in 1.28s). Extended Playwright E2E suite: **15/15 E2E tests passed (20.9s)**. |
| **15** | **Final Integration & Regression Audit** | [x] **COMPLETE** | Comprehensive end-to-end integration and regression audit completed. Verified zero duplicate subsystems (authoritative single injection hard gate, 5-tier hierarchical memory, strict MCP gateway), zero dead routes, zero decorative UI elements, and enforced air-gapped offline isolation at the socket boundary. Executed full test suites: **190/190 backend unit & integration tests passed (78.3s)**, **78/78 evaluation & security benchmark tests passed (22.1s)**, **15/15 Playwright browser E2E tests passed (18.1s)**, **8/8 provenance completeness & offline isolation tests passed (27.8s)**, and performance benchmark successfully validated against `PERFORMANCE_BUDGETS.md`. |
| **16** | **Final Local Release & Packaging** | [x] **COMPLETE** | Automated unified release gate runners created (`scripts/run_full_gate.ps1`, `scripts/run_full_gate.sh`), unified system background launcher created (`scripts/start_system.ps1`), clean shutdown script created (`scripts/stop_system.ps1`), and official 41-point release gate sign-off compiled in `RELEASE_GATE_SIGNOFF.md`. Full 6-stage release gate verified with **100% PASS** across all functional, security, AI quality, performance, persistence, frontend, and engineering criteria. |

---

## Detailed Summary of Phase Implementations

### Phase 01: Centralized Configuration & System Prompt Registry
- **`backend/app/config/settings.py`**:
  - `ModelConfig`: Centralized default model (`gemma2:2b`), fallback model (`qwen2.5:3b`), timeouts, context tokens, and GPU layer offload settings.
  - `SecurityConfig`: Injection risk threshold (0.7), grounding overlap threshold (0.05), PII scanning flags, and allowed CORS origins.
  - `RetrievalConfig`: Chroma persistence directory, upload limits (10MB / 100 pages), citation max chars, RRF constant.
  - `MemoryConfig`: SQLite audit path, transcript memory path, PostgreSQL connection string, Redis URL.
  - `MCPConfig`: Tool permissions path, enabled MCP servers (`StitchMCP`, `code-review-graph`, `firebase-mcp-server`).
  - `PerformanceConfig`: Hardware telemetry cache TTL, token budget safety margins.
  - `NetworkModeConfig`: Default network mode `OFFLINE` with `legal_sources.yaml` path.
- **Direct Settings Injection**:
  - `Layer1InputGuard` defaults to `settings.INJECTION_RISK_THRESHOLD` and `settings.security.max_query_chars`.
  - `Layer2TrustedContext` defaults to `settings.ENABLE_PII_SCANNING` and `settings.security.pii_entities`.
  - `Layer3OutputGuard` defaults to `settings.GROUNDING_OVERLAP_THRESHOLD`.
  - `TokenBudgetManager` defaults to `settings.GENERATOR_CONTEXT_TOKENS` and `settings.GENERATOR_MAX_OUTPUT_TOKENS`.
  - `fuse_bm25_dense` defaults to `settings.retrieval.rrf_k` and `settings.retrieval.top_k`.
  - `HardwareDetector.get_auto_selected_tier` dynamically queries `ModelRegistry`.
- **YAML Registries**:
  - `backend/app/config/model_registry.yaml`
  - `backend/app/config/mcp_permissions.yaml`
  - `backend/app/config/legal_sources.yaml`
- **Versioned Prompts**:
  - `backend/app/prompts/` with immutable `security_core.md`, `legal_behavior.md`, `retrieval_instructions.md`, `tool_policy.md`, `citation_requirements.md`, `task_template.md`, and deterministic `assembler.py`.
- **Validation**:
  - `pytest tests/config/ -v`: **10/10 tests passed**.
  - `pytest -v` (Full backend test suite): **55 passed in 42.08s**.

### Phase 02: Persistence & PostgreSQL Production Layer
- **`backend/app/db/engine.py`**:
  - Async SQLAlchemy engine (`create_async_engine`) and sync engine (`create_engine`) with configurable QueuePool / NullPool and bounded connection timeouts (3.0s).
  - `get_db_session()` and `get_sync_session()` transaction context managers with auto-rollback boundaries.
- **`backend/app/db/models.py`**:
  - Declarative SQLAlchemy models: `Conversation`, `Message`, `SemanticMemory`, `DocumentMemory`, `ResearchSession`, `ResearchSource`, `AuditEvent`.
  - Foreign keys, cascade delete on messages, composite indexes (`user_id, category, key`).
- **`backend/app/memory/durable_memory.py`**:
  - Refactored to utilize declarative SQLAlchemy ORM models with write-through persistence and identity isolation.
  - Implemented CRUD for conversations, messages, semantic memory facts/preferences, and document metadata memory.
- **`backend/app/defense/audit_log.py`**:
  - Refactored to persist cryptographic SHA-256 hash-chained events using the `AuditEvent` ORM model.
- **`backend/app/routes/upload.py`**:
  - Document metadata memory saved on single and batch PDF uploads; added `GET /memory/documents/{session_id}` route.
- **`backend/app/routes/chat.py`**:
  - Added semantic memory endpoints (`GET /chat/memory/semantic`, `POST /chat/memory/semantic`) and turn latency/blocked_by tracking.
- **`backend/app/db/health.py`**:
  - `check_db_health()` with `asyncio.wait_for` 2.5s bounded timeout and pool connection telemetry.
  - `GET /health/db` endpoint reporting status, query latency, and pool statistics.
- **Validation**:
  - `pytest tests/test_db_persistence.py tests/test_stage3_memory.py -v`: **11/11 passed in 1.58s**.
  - `pytest tests/test_defense_layers.py -v`: **10/10 passed in 38.67s**.
  - `pytest -v` (Full backend test suite): **55 passed in 42.08s**.

### Phase 06: Retrieval Optimization & Hybrid RAG
- **Persistent BM25 Index (`backend/app/retrieval/bm25_index.py`)**:
  - Serialized `BM25Plus` sparse index persisted to disk (`./bm25_index/`), eliminating per-query rebuild overhead.
  - Supports incremental single and batch document additions and removals.
- **Fusion Router (`backend/app/retrieval/fusion_router.py`)**:
  - Automatically classifies queries into `pageindex` (structural hierarchy), `hybrid` (dense + BM25 + RRF), or `both`.
  - Extracts direct Act/Chapter/Section identifiers for instant structural lookups.
- **Deduplication & Superseded Filtering**:
  - `deduplicate_chunks` performs Jaccard similarity thresholding (0.85) to eliminate duplicate provisions.
  - `filter_superseded_provisions` dynamically excludes repealed laws and superseded amendments.
- **Benchmark Suite (`backend/app/retrieval/metrics.py`)**:
  - Accuracy metrics calculating Recall@K, Precision@K, MRR, nDCG, and Citation Hit Rate.
- **Validation**:
  - `pytest tests/retrieval/ -v`: **19/19 passed**.

### Phase 07: Defensive Security Upgrade
- **Layer 1 Hard Gate (`backend/app/security/injection_gate.py`)**:
  - Strict non-additive risk evaluation rejecting prompt injections, SQLi, command injection, and directory traversal.
  - Request-scoped query hash caching to eliminate redundant Layer 1 / Layer 1.5 scans.
- **Unified Context Sanitizer (`backend/app/security/context_sanitizer.py`)**:
  - Sanitizes untrusted text across retrieved corpus chunks, uploaded documents, and MCP/web tool results.
  - Strips embedded control instructions, script tags, and safely wraps content into `<data>` tags.
- **PDF Security Ingestion (`backend/app/security/pdf_sanitizer.py`)**:
  - Validates `%PDF` magic bytes, enforces file size (10MB) and page count (100) quotas, and blocks active executable objects (`/JavaScript`, `/Launch`).
- **Unconditional PII Scanner (`backend/app/security/pii_scanner.py`)**:
  - Ingestion and output defense-in-depth scanner redacting Aadhaar, PAN, phone numbers, and emails with Presidio and fallback regex.
- **Output Validator & Guardrails (`backend/app/security/output_validator.py`)**:
  - Deterministic Jaccard token overlap grounding and citation existence checking against corpus metadata.
  - System leak detection and structured response schema validation.
- **Cryptographic Audit Ledger (`backend/app/security/audit_ledger.py`)**:
  - SHA-256 hash chaining verification with `verify_chain()` diagnostic traversal.
  - Mounted `GET /audit/verify` REST endpoint.
- **Validation**:
  - `pytest tests/security/ -v`: **22/22 passed**.
  - **Full Regression Suite**: **108/108 passed in 34.32s**.

### Phase 08: MCP Gateway & Tools Integration
- **Tool Registry (`backend/app/mcp/tool_registry.py`)**:
  - Registered typed tool definitions with strict Pydantic input and output schemas across all 7 formal categories (`LOCAL_RETRIEVAL`, `DOCUMENT_SEARCH`, `LEGAL_SEARCH`, `CURRENT_LAW`, `CASE_LAW_SEARCH`, `GOVERNMENT_SOURCE`, `DEEP_RESEARCH`) and external servers (`StitchMCP`, `code-review-graph`, `firebase-mcp-server`).
- **Policy Engine (`backend/app/mcp/policy_engine.py`)**:
  - Enforces category allowlists from `mcp_permissions.yaml`, network mode restrictions (blocking online tools when mode is `OFFLINE`), request call quotas, and server explicit deny lists (`delete_project`, `firebase_deploy`).
- **Permission Layer (`backend/app/mcp/permission_layer.py`)**:
  - Validates request payloads and response outputs against Pydantic models before and after dispatch, preventing out-of-schema or malformed payloads from reaching servers.
- **MCP Gateway (`backend/app/mcp/gateway.py`)**:
  - Dispatches tool invocations with per-call timeouts, recursive defense-in-depth context sanitization (stripping prompt injections, jailbreaks, script tags), database persistence to `mcp_tool_calls`, and append-only L6 audit logging.
- **API & Dynamic UI (`backend/app/routes/mcp.py` & `McpToolsView.jsx`)**:
  - Mounted `GET /mcp/status`, `POST /mcp/tool-call`, and `GET /mcp/history` routes.
  - Connected `McpToolsView.jsx` and `apiClient.getMcpStatus()` to display real-time backend state, categories, active servers, and permission policies.
- **Validation**:
  - `pytest tests/mcp/ -v`: **15/15 passed**.
  - **Full System Regression Suite**: **123/123 passed in 42.41s**.

### Phase 09: Bounded Agentic Research Orchestrator
- **State Machine Engine (`backend/app/orchestrator/state_machine.py`)**:
  - Implemented formal Finite State Machine with strictly code-controlled transitions:
    `INITIALIZED` -> `CLASSIFY` -> `SECURITY_CHECK` -> `PLAN` -> `RETRIEVE` -> `TOOL_CALL` -> `EVIDENCE_VALIDATION` -> `SYNTHESIS` -> `LEGAL_VERIFICATION` -> `COMPLETED`.
  - Rejects any out-of-graph state transitions; LLM does not decide the next state via unconstrained free-text.
- **Execution Ceilings (`backend/app/orchestrator/limits.py`)**:
  - Strict typed limit enforcement (`LimitExceeded`, `StepLimitExceeded`, `ToolCallLimitExceeded`, `TokenLimitExceeded`, `TimeLimitExceeded`, `DocLimitExceeded`, `NetworkLimitExceeded`, `RetryBudgetExceeded`).
  - Budget tracker monitors step count, tool dispatches, tokens, wall-clock time, retrieved docs, and network requests.
- **Step-Type Circuit Breaker (`backend/app/orchestrator/circuit_breaker.py`)**:
  - Tracks consecutive failures per step type. Trips to `OPEN` after 3 consecutive failures, cleanly degrading to local statutory retrieval without hanging or crashing. Cooldown automatic recovery to `HALF_OPEN` and `CLOSED`.
- **Cancellation Manager (`backend/app/orchestrator/cancellation.py`)**:
  - Handles user-initiated (`POST /research/cancel/{id}`) and timeout cancellation, preventing orphaned tool calls and marking L5 `ResearchSession` status as `cancelled`.
- **Chat Pipeline Integration & Rollback Switch**:
  - Integrated into `chat_endpoint` in `backend/app/routes/chat.py` with backward-compatible rollback fallback when `settings.orchestrator.enabled` is false.
- **Validation**:
  - `pytest tests/orchestrator/ -v`: **20/20 passed**.
  - **Full System Regression Suite**: **143/143 passed in 62.91s**.

### Phase 10: Online/Offline Legal Research & Current-Law Handling
- **Hard Network Policy Boundary (`backend/app/network/mode_enforcer.py`)**:
  - OFFLINE mode provably blocks 100% of outbound external HTTP/socket calls with cryptographic L6 audit logging.
  - ONLINE mode permits requests ONLY to allowlisted domains from `legal_sources.yaml` with strict TLS verification.
  - Comprehensive SSRF defense gate blocking loopback (`127.0.0.1`), private RFC1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), and AWS/cloud metadata endpoints (`169.254.169.254`).
- **Cryptographic Provenance Schema (`backend/app/research/provenance.py`)**:
  - Mandatory 13-field provenance record (`source_id`, `source_type`, `source_title`, `source_url`, `jurisdiction`, `act`, `section`, `document_version`, `publication_date`, `retrieval_timestamp`, `content_hash`, `trust_level`, `retrieval_method`).
  - Strict validation invariant: any evidence chunk lacking complete mandatory provenance fields is discarded.
- **Freshness Detection Engine (`backend/app/research/freshness.py`)**:
  - Deterministic keyword heuristics and corpus metadata verification checks (`last_verified_at` > 90 days or `is_superseded=True`).
- **Legal Conflict Detector (`backend/app/research/conflict_detector.py`)**:
  - Cross-matches online gazette/enactment records against local corpus provisions to detect `STATUS_CONFLICT` and `AMENDMENT_OVERWRITE` (e.g. IPC replaced by BNS 2023). Surfaces both provisions with guidance rather than silently overwriting.
- **10-Step Bounded Research Pipeline (`backend/app/research/pipeline.py`)**:
  - Orchestrated pipeline with OFFLINE mode freshness warnings and Layer 3 output validation.
- **REST Endpoints (`backend/app/routes/research.py`)**:
  - Mounted `GET /research/mode`, `POST /research/mode`, and `POST /research/pipeline`.
- **Validation**:
  - `pytest tests/network/ tests/research/ -v`: **18/18 passed**.
  - **Full System Regression Suite**: **161/161 passed in 101.24s**.

### Phase 11: Observability & Benchmarking
- **Correlation ID Tracking (`backend/app/observability/correlation.py`)**:
  - `CorrelationMiddleware` attaches `X-Correlation-ID` header and propagates context variable across all async operations.
- **Confidentiality Redactor (`backend/app/observability/redaction.py`)**:
  - Unconditionally strips raw prompt and document content from metrics and telemetry payloads, recording only token counts, character lengths, and SHA-256 hashes. Redacts PII from log messages.
- **Metrics Collection & Ring Buffer (`backend/app/observability/metrics.py`)**:
  - Maintains in-memory bounded ring buffer (`maxlen=1000`) and persists to `request_metrics` DB table. Computes p50, p95, p99, TTFT, and cache hit rates.
- **Diagnostics Dashboard Routes (`backend/app/routes/diagnostics.py`)**:
  - Mounted `GET /diagnostics`, `GET /diagnostics/trace/{request_id}`, `GET /diagnostics/metrics/recent`, and `GET /diagnostics/metrics/summary`.
- **Empirical Hardware Benchmarks & Performance Budgets (`PERFORMANCE_BUDGETS.md`)**:
  - Automated benchmark runner (`python -m app.observability.benchmark --tier=0`) tested cold start, retrieval latency (BM25 vs Dense vs RRF), TTFT, and concurrency throughput (1, 2, 5 clients), generating concrete empirical SLA baselines.
- **Validation**:
  - `pytest tests/observability/ -v`: **11/11 passed**.
  - **Full System Regression Suite**: **172/172 passed in 83.16s**.
