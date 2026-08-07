# Stage 5 — Intelligent Runtime & Knowledge Orchestration

> **This stage makes the platform model-agnostic, hardware-aware, and production-ready at the
> runtime layer.** Stages 1–4 built security, ingestion, retrieval, and defense. Stage 5 builds
> the intelligence layer that sits between the knowledge store and the user: hardware detection,
> model management, context assembly, prompt orchestration, streaming, citation, and output
> verification.
>
> **Core principle:** Knowledge lives in the retrieval layer. The LLM is a replaceable reasoning
> engine. Legal amendments, court judgments, and user uploads update the knowledge store — they
> never require model changes, retraining, or adapter generation.
>
> **Prerequisite:** Stages 1–4 stable. All tests in `tests/` passing. The Stage 2/3 retrieval
> eval harness (`tests/eval/retrieval_eval.py`) showing a healthy recall and MRR baseline.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 5 — RUNTIME LAYER                          │
│                                                                     │
│  Browser / Client                                                   │
│       │                                                             │
│  ┌────▼────────────────────────────────────────────────┐           │
│  │  Frontend (React/Vite)                              │           │
│  │  Streaming response renderer                        │           │
│  │  Citation panel / Confidence badge                  │           │
│  │  Model selector (hardware-aware)                    │           │
│  └────┬────────────────────────────────────────────────┘           │
│       │ SSE / REST                                                  │
│  ┌────▼────────────────────────────────────────────────┐           │
│  │  5.A  Hardware Detection & Benchmarking              │           │
│  │  5.B  Model Registry & Compatibility Matrix          │           │
│  │  5.C  Model Download Manager (Ollama / HF)           │           │
│  │  5.D  Runtime Abstraction Layer                      │           │
│  │       ├─ OllamaRuntime                              │           │
│  │       ├─ LlamaCppRuntime                            │           │
│  │       └─ TransformersRuntime                        │           │
│  │  5.E  Runtime Manager & Health Monitor              │           │
│  │  5.F  Context Builder & Prompt Orchestrator         │           │
│  │  5.G  Token Budget Manager                          │           │
│  │  5.H  Streaming Response Engine                     │           │
│  │  5.I  Citation Builder                              │           │
│  │  5.J  Output Verifier (Hallucination / Confidence)  │           │
│  │  5.K  Response Formatter                            │           │
│  └────┬────────────────────────────────────────────────┘           │
│       │                                                             │
│  ┌────▼────────────────────────────────────────────────┐           │
│  │  Knowledge Store (Stages 1–4, unchanged)            │           │
│  │  pgvector + ChromaDB fallback + BM25                │           │
│  │  Redis session memory                               │           │
│  │  Postgres audit + chat history                      │           │
│  └─────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The One Constraint That Cannot Move

**No knowledge lives inside the model.** The model is a reasoning engine only. Every legal
fact, every statute section, every court judgment, every user document is stored in the
retrieval layer (pgvector / ChromaDB). When law changes, the knowledge store is updated.
The model is never retrained. The model is never modified. The model is swapped if something
better exists.

This is the correct enterprise RAG architecture. Fine-tuning, LoRA adapters, and adapter
training are not part of this runtime. They are not listed as "future" steps — they are
explicitly outside the design because they would couple the knowledge lifecycle to the model
lifecycle.

---

## 5.A — Hardware Detection & Benchmarking

> The runtime must know what hardware it is running on before recommending or downloading
> a model. A recommendation that requires 16 GB VRAM on a machine with 8 GB will fail silently.
> Hardware detection must run at startup and must be queryable by the frontend.

### 5.A.1 Hardware Detection Module

New module: `backend/app/system/hardware_detector.py`

```python
class HardwareProfile:
    cpu_cores: int
    cpu_name: str
    ram_total_gb: float
    ram_available_gb: float
    gpu_available: bool
    gpu_name: str | None
    gpu_vram_gb: float | None
    gpu_backend: str | None          # "cuda" | "rocm" | "metal" | None
    storage_free_gb: float
    platform: str                    # "windows" | "linux" | "macos"
    supports_avx2: bool              # required for most GGUF quantizations

class HardwareDetector:
    def detect(self) -> HardwareProfile:
        # CPU: psutil.cpu_count(), cpuinfo for name and AVX2 flag
        # RAM: psutil.virtual_memory()
        # GPU: attempt torch.cuda.is_available() + nvidia-smi subprocess
        #      fallback to platform-native tools (macOS: metal via torch.backends.mps)
        # Storage: psutil.disk_usage(MODELS_DIR)
        # Cache result for HARDWARE_CACHE_TTL_SECONDS (default 300)
        ...

    def benchmark(self) -> dict:
        # Run a small token generation benchmark against the current active model
        # Returns: tokens_per_second, time_to_first_token_ms
        # Used to update the model recommendation tier dynamically
        ...
```

### 5.A.2 Hardware Profile API

```
GET /system/hardware      -> HardwareProfile (cached)
GET /system/benchmark     -> BenchmarkResult (runs live benchmark, may take 10–30s)
```

The hardware profile is injected into model recommendation (5.B) and is surfaced in the
frontend settings panel as a read-only system info card.

**Add to `.env.example` and `config.py`:**

```ini
HARDWARE_CACHE_TTL_SECONDS=300
MODELS_DIR=./models
```

---

## 5.B — Model Registry & Compatibility Matrix

> The model registry is the single authoritative source for which models exist, which models
> are supported, and which models are appropriate for a given hardware profile. It replaces
> the ad-hoc `MODEL_CATALOG` dict used in Stage 4.

### 5.B.1 Model Registry Schema

New module: `backend/app/system/model_registry.py`

```python
class ModelEntry:
    model_id: str                    # unique key: "qwen2.5:7b", "llama3.2:3b", etc.
    display_name: str
    provider: str                    # "ollama" | "huggingface" | "llamacpp"
    size_gb: float                   # download size
    ram_required_gb: float           # minimum RAM for CPU inference
    vram_required_gb: float | None   # minimum VRAM for GPU inference; None = CPU-only
    context_window: int              # max context tokens
    quantization: str                # "q4_k_m" | "q8_0" | "f16" | "bf16"
    language_support: list[str]      # ["en", "hi"] — for multilingual models
    tier: str                        # "minimum" | "standard" | "recommended" | "premium"
    requires_avx2: bool
    ollama_tag: str | None           # "qwen2.5:7b" for ollama pull
    hf_repo: str | None              # "Qwen/Qwen2.5-7B-Instruct" for HF download
    gguf_filename: str | None        # specific GGUF file if using llama.cpp
    benchmark_tokens_per_sec: dict   # {"minimum": 5, "standard": 12, "recommended": 20}

class ModelRegistry:
    def all_models(self) -> list[ModelEntry]: ...
    def recommended_for(self, hw: HardwareProfile) -> list[ModelEntry]: ...
    def get(self, model_id: str) -> ModelEntry | None: ...
    def is_downloaded(self, model_id: str) -> bool: ...
    def downloaded_models(self) -> list[str]: ...
```

### 5.B.2 Compatibility Matrix Logic

When `recommended_for(hw)` is called:

1. Filter: `ram_required_gb <= hw.ram_available_gb * 0.85` (leave 15% headroom)
2. Filter: if `hw.gpu_available`, also consider `vram_required_gb <= hw.gpu_vram_gb * 0.85`
3. Filter: `requires_avx2 == False OR hw.supports_avx2 == True`
4. Sort by tier descending, then by context_window descending
5. Return top 5 results — the first is the auto-selected recommendation

The existing `GET /recommend` endpoint is updated to use `ModelRegistry.recommended_for()`
instead of the static dict. No breaking change to the API contract.

### 5.B.3 Registry Data File

The registry is defined as a YAML file, not hardcoded Python, so it can be updated without
code changes:

File: `backend/data/model_registry.yaml`

```yaml
models:
  - model_id: "qwen2.5:3b"
    display_name: "Qwen 2.5 3B"
    provider: "ollama"
    size_gb: 2.0
    ram_required_gb: 4.0
    context_window: 8192
    quantization: "q4_k_m"
    language_support: ["en", "hi", "zh"]
    tier: "minimum"
    requires_avx2: false
    ollama_tag: "qwen2.5:3b"

  - model_id: "qwen2.5:7b"
    display_name: "Qwen 2.5 7B"
    provider: "ollama"
    size_gb: 4.7
    ram_required_gb: 8.0
    context_window: 8192
    quantization: "q4_k_m"
    tier: "standard"
    requires_avx2: false
    ollama_tag: "qwen2.5:7b"

  - model_id: "llama3.2:3b"
    display_name: "Llama 3.2 3B"
    provider: "ollama"
    size_gb: 2.0
    ram_required_gb: 4.0
    context_window: 8192
    tier: "minimum"
    ollama_tag: "llama3.2:3b"

  - model_id: "gemma2:9b"
    display_name: "Gemma 2 9B"
    provider: "ollama"
    size_gb: 5.4
    ram_required_gb: 12.0
    context_window: 8192
    tier: "recommended"
    ollama_tag: "gemma2:9b"

  - model_id: "mistral:7b"
    display_name: "Mistral 7B"
    provider: "ollama"
    size_gb: 4.1
    ram_required_gb: 8.0
    context_window: 8192
    tier: "standard"
    ollama_tag: "mistral:7b"
```

This file ships in the repository and is loaded at startup. Updates to the registry (new
models, corrected specs) are delivered via git pull, not code changes.

---

## 5.C — Model Download Manager

> A model must be downloadable through the UI and immediately usable once downloaded. No
> post-download steps. No training. No conversion. Pull → ready.

### 5.C.1 Download Flow

```
User selects model in UI
        ↓
POST /models/pull { model_id: "qwen2.5:7b" }
        ↓
ModelDownloadManager resolves provider from ModelRegistry
        ↓
   provider = "ollama"    →  OllamaDownloadClient.pull(ollama_tag)
   provider = "huggingface" → HFDownloadClient.download(hf_repo, gguf_filename)
   provider = "llamacpp"  →  LlamaCppDownloadClient.download(gguf_url)
        ↓
Progress streamed via SSE: GET /models/pull/progress/{task_id}
        ↓
On completion: model registered as available in RuntimeManager (5.E)
Model immediately usable — no further steps
```

### 5.C.2 Download Manager Module

New module: `backend/app/system/model_download_manager.py`

```python
class ModelDownloadManager:
    async def pull(self, model_id: str) -> str:
        # Returns task_id for progress tracking
        entry = self.registry.get(model_id)
        if not entry:
            raise ValueError(f"Unknown model: {model_id}")

        task_id = str(uuid.uuid4())
        asyncio.create_task(self._run_download(task_id, entry))
        return task_id

    async def _run_download(self, task_id: str, entry: ModelEntry):
        # Updates Redis key "dl:{task_id}" with progress JSON
        # {status: "downloading", percent: 42, bytes_downloaded: ..., eta_seconds: ...}
        # On completion: {status: "done"}
        # On error: {status: "error", message: "..."}
        ...
```

Existing `POST /models/pull` and `GET /models/pull/progress/{task_id}` endpoints are refactored
to use `ModelDownloadManager` instead of the current inline logic. No API contract change.

---

## 5.D — Runtime Abstraction Layer

> One interface, three backends. `chat.py` calls `runtime.generate()`. It does not know or care
> whether the backend is Ollama, llama.cpp, or HuggingFace Transformers.

### 5.D.1 Runtime Protocol

New module: `backend/app/runtime/base.py`

```python
from typing import Protocol, AsyncIterator

class LLMRuntime(Protocol):
    """
    The only interface chat.py is allowed to call.
    Every backend must implement exactly these two methods.
    """
    async def generate(self, prompt: str, model: str, **kwargs) -> str:
        """Full response, non-streaming."""
        ...

    async def generate_stream(self, prompt: str, model: str, **kwargs) -> AsyncIterator[str]:
        """Token stream. Yields one token (or small chunk) at a time."""
        ...

    async def health_check(self) -> bool:
        """Returns True if the backend is reachable and the model is loaded."""
        ...
```

### 5.D.2 Ollama Runtime

New module: `backend/app/runtime/ollama_runtime.py`

Wraps the existing `OllamaClient` (unchanged) into the `LLMRuntime` protocol.
No behavior change. Zero migration cost for existing functionality.

```python
class OllamaRuntime:
    def __init__(self):
        self._client = OllamaClient(settings.OLLAMA_URL, settings.DEFAULT_MODEL)

    async def generate(self, prompt: str, model: str, **kwargs) -> str:
        return await self._client.generate(prompt, model=model)

    async def generate_stream(self, prompt: str, model: str, **kwargs):
        async for token in self._client.generate_stream(prompt, model=model):
            yield token

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(f"{settings.OLLAMA_URL}/api/version")
                return r.status_code == 200
        except Exception:
            return False
```

### 5.D.3 llama.cpp Runtime

New module: `backend/app/runtime/llamacpp_runtime.py`

Uses `llama-cpp-python` (pure Python bindings, no separate binary required if using the
wheel distribution). Falls back to Ollama if llama.cpp is not installed.

```python
class LlamaCppRuntime:
    def __init__(self, model_path: str):
        try:
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=model_path,
                n_ctx=settings.GENERATOR_CONTEXT_TOKENS,
                n_gpu_layers=-1 if settings.LLAMACPP_GPU else 0,
                verbose=False,
            )
            self._available = True
        except ImportError:
            logger.warning("llama-cpp-python not installed. LlamaCppRuntime unavailable.")
            self._available = False

    async def generate(self, prompt: str, model: str, **kwargs) -> str:
        if not self._available:
            raise RuntimeError("llama.cpp not available")
        output = self._llm(prompt, max_tokens=settings.GENERATOR_MAX_OUTPUT_TOKENS)
        return output["choices"][0]["text"].strip()

    async def generate_stream(self, prompt: str, model: str, **kwargs):
        if not self._available:
            raise RuntimeError("llama.cpp not available")
        for chunk in self._llm(prompt, max_tokens=settings.GENERATOR_MAX_OUTPUT_TOKENS, stream=True):
            token = chunk["choices"][0]["text"]
            if token:
                yield token
```

### 5.D.4 HuggingFace Transformers Runtime

New module: `backend/app/runtime/transformers_runtime.py`

Refactored from the existing `TransformersGenerator` in `model/generator.py`. Same fallback
chain: if `transformers` is not installed, falls back to OllamaRuntime.

### 5.D.5 Runtime Factory

New module: `backend/app/runtime/factory.py`

```python
def build_runtime() -> LLMRuntime:
    """
    Reads MODEL_RUNTIME from settings.
    Builds and returns the appropriate runtime.
    Falls back in order: Ollama → Transformers → raises clear error.
    """
    runtime_name = settings.MODEL_RUNTIME.lower()

    if runtime_name == "ollama":
        return OllamaRuntime()

    if runtime_name == "llamacpp":
        model_path = _resolve_model_path(settings.DEFAULT_MODEL)
        return LlamaCppRuntime(model_path=model_path)

    if runtime_name == "transformers":
        return TransformersRuntime()

    if runtime_name == "mock":
        return MockRuntime()

    logger.warning(f"Unknown MODEL_RUNTIME={runtime_name!r}, defaulting to Ollama.")
    return OllamaRuntime()
```

**In `chat.py`:** replace `build_generator()` with `build_runtime()` throughout. The call
site changes from `generator.generate(prompt, model=model)` to `runtime.generate(prompt, model)`.
Functionally identical. No response format change.

**Add to `.env.example` and `config.py`:**

```ini
MODEL_RUNTIME=ollama           # ollama | llamacpp | transformers | mock
LLAMACPP_GPU=false             # enable GPU layers for llama.cpp
LLAMACPP_MODEL_PATH=           # absolute path to .gguf file (for llamacpp runtime)
```

---

## 5.E — Runtime Manager & Health Monitor

> The RuntimeManager holds the active runtime instance and exposes health information. It
> handles runtime switching at runtime (without restart) and exposes the current backend
> state to the frontend.

### 5.E.1 Runtime Manager

New module: `backend/app/runtime/runtime_manager.py`

```python
class RuntimeManager:
    """
    Singleton. Built once at application startup.
    Holds the active LLMRuntime instance.
    Supports hot-switching between runtimes.
    """
    _instance: LLMRuntime = None

    @classmethod
    def get(cls) -> LLMRuntime:
        if cls._instance is None:
            cls._instance = build_runtime()
        return cls._instance

    @classmethod
    def switch(cls, runtime_name: str, **kwargs) -> None:
        """Switch the active runtime without restarting the server."""
        settings.MODEL_RUNTIME = runtime_name
        cls._instance = build_runtime(**kwargs)

    @classmethod
    async def health(cls) -> dict:
        runtime = cls.get()
        is_healthy = await runtime.health_check()
        return {
            "runtime": settings.MODEL_RUNTIME,
            "model": settings.DEFAULT_MODEL,
            "healthy": is_healthy,
        }
```

### 5.E.2 Runtime Health API

```
GET  /runtime/health          -> RuntimeHealthResponse
POST /runtime/switch          -> switch runtime + model without restart
GET  /runtime/active          -> active runtime name + model
```

The existing `GET /health` endpoint is extended to include `runtime` status from
`RuntimeManager.health()`. No breaking change.

---

## 5.F — Context Builder & Prompt Orchestrator

> The context builder assembles the full prompt from multiple sources in a defined priority
> order. The prompt orchestrator applies the defense layers and formats the final prompt
> string for the active runtime.

### 5.F.1 Context Assembly Priority

The context is assembled in this fixed order (top = highest priority in prompt):

```
1. SYSTEM INSTRUCTION BLOCK
   - Role definition (legal assistant)
   - Behavioral constraints (cite only what is retrieved)
   - Refusal instruction (if no context, say so — never fabricate)

2. USER PROFILE BLOCK (permanent, loaded from Postgres)
   - Firm name, practice areas
   - Current matter name and type

3. CONVERSATION SUMMARY (if session has >10 prior turns)
   - Rolling summary generated from older turns

4. RECENT CONVERSATION HISTORY (last 5 turns from Redis)
   - Formatted as "User: ... / Assistant: ..."

5. RETRIEVED KNOWLEDGE CHUNKS (from Stage 2/3 retrieval)
   - Tier-1 corpus chunks (trust_score >= 0.9)
   - Tier-2 user document chunks (trust_score >= 0.6)
   - Each chunk tagged with: Act, Section, Source, TrustScore

6. USER QUERY
```

### 5.F.2 Context Builder Module

New module: `backend/app/runtime/context_builder.py`

```python
class ContextBuilder:
    def build(
        self,
        query: str,
        retrieved_chunks: list[dict],
        user_profile: UserProfile | None,
        history: list[dict],
        summary: str,
    ) -> ContextPackage:
        """
        Returns a ContextPackage containing:
        - full_prompt: str (the assembled prompt string)
        - token_count: int (estimated tokens in the prompt)
        - chunks_included: list[dict] (chunks that fit within the budget)
        - chunks_truncated: int (chunks dropped due to token budget)
        """
        ...
```

### 5.F.3 Prompt Templates

New directory: `backend/app/runtime/templates/`

```
templates/
  system_instruction.txt      # base system prompt (legal assistant role)
  user_profile_block.txt      # {firm_name}, {practice_areas}, {matter_name}
  citation_format.txt         # how to cite: "Section X, Act Y (Year)"
  refusal_format.txt          # what to say when no context retrieved
```

Templates are loaded at startup. They can be edited without code changes. They are not
exposed to the API — they are internal prompt engineering artifacts.

---

## 5.G — Token Budget Manager

> Context windows are finite. The token budget manager ensures the assembled context always
> fits within the active model's context window. If it does not fit, chunks are dropped in
> reverse priority order (lowest trust score first).

### 5.G.1 Token Budget Rules

```
TOTAL_BUDGET = model.context_window - GENERATOR_MAX_OUTPUT_TOKENS - SAFETY_MARGIN_TOKENS

Fixed cost (never truncated):
  system_instruction_tokens + user_profile_tokens + query_tokens + history_tokens

Flexible budget (trimmed when over limit):
  retrieved_chunk_tokens

Trimming strategy:
  1. Drop lowest trust_score chunks first
  2. Within equal trust_score, drop longest chunks first
  3. Never drop Tier-1 corpus chunks if Tier-2 user chunks can be dropped instead
  4. Hard minimum: 1 chunk must always remain (never send zero context to the model)
```

### 5.G.2 Token Estimator

```python
class TokenBudgetManager:
    def __init__(self, model_entry: ModelEntry):
        self.budget = (
            model_entry.context_window
            - settings.GENERATOR_MAX_OUTPUT_TOKENS
            - settings.TOKEN_BUDGET_SAFETY_MARGIN
        )
        # Use tiktoken cl100k_base as a universal token estimator
        # Actual tokenizer varies by model but cl100k gives a safe upper bound

    def fit_chunks(self, fixed_tokens: int, chunks: list[dict]) -> tuple[list[dict], int]:
        """Returns (chunks_that_fit, n_dropped)"""
        ...
```

**Add to `.env.example` and `config.py`:**

```ini
TOKEN_BUDGET_SAFETY_MARGIN=256
```

---

## 5.H — Streaming Response Engine

> Legal queries produce long answers. Streaming eliminates the perception of a "hanging" UI.
> The existing `/chat/stream` endpoint is correct in concept but needs to be wired through the
> new RuntimeManager and emit properly formatted SSE with citation metadata.

### 5.H.1 SSE Event Format

```
data: {"type": "token", "content": "Under Section"}
data: {"type": "token", "content": " 302"}
...
data: {"type": "citation", "act": "IPC", "section": "302", "trust_score": 0.94}
data: {"type": "done", "blocked_by": null, "confidence": 0.87}
```

The frontend receives:
- `token` events: append to the message bubble in real time
- `citation` events: populate the citations panel without re-rendering
- `done` event: finalize the bubble, show confidence badge, enable the export button

### 5.H.2 Streaming Implementation

In `chat.py`, the shield-on path is updated to:

```python
async def shielded_stream_generator():
    generator = RuntimeManager.get()
    full_answer = []
    async for token in generator.generate_stream(prompt, model=request.model):
        full_answer.append(token)
        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

    answer = "".join(full_answer)

    # Run output guard on completed answer
    is_valid, reason = output_guard.validate(answer, scored_chunks, prompt)
    if not is_valid:
        yield f"data: {json.dumps({'type': 'error', 'message': reason})}\n\n"
    else:
        for src in sources:
            yield f"data: {json.dumps({'type': 'citation', **src.dict()})}\n\n"
        confidence = confidence_scorer.score(answer, scored_chunks)
        yield f"data: {json.dumps({'type': 'done', 'confidence': confidence})}\n\n"

    yield "data: [DONE]\n\n"
```

---

## 5.I — Citation Builder

> Citations are not extracted from the model's answer text. They are built from the retrieved
> chunks that were actually passed into the prompt. This is guaranteed grounding — the citation
> always refers to something the model saw.

### 5.I.1 Citation Builder Module

New module: `backend/app/runtime/citation_builder.py`

```python
class CitationBuilder:
    def build(self, chunks_used: list[dict]) -> list[CitationSource]:
        """
        For each chunk that was included in the prompt, produce a CitationSource.
        Deduplicates by (act, section).
        Sorts by trust_score descending.
        Truncates text to 500 chars (config: CITATION_TEXT_MAX_CHARS).
        """
        seen = set()
        citations = []
        for chunk in sorted(chunks_used, key=lambda c: c.get("trust_score", 0), reverse=True):
            key = (chunk.get("act", ""), chunk.get("section", ""))
            if key in seen:
                continue
            seen.add(key)
            citations.append(CitationSource(
                act=chunk.get("act", "Unknown"),
                section=chunk.get("section", ""),
                text=chunk["text"][:settings.CITATION_TEXT_MAX_CHARS],
                similarity_score=chunk.get("similarity_score"),
                trust_score=chunk.get("trust_score"),
                freshness_score=chunk.get("freshness_score"),
                injection_risk_score=chunk.get("injection_risk_score"),
                confidence_score=chunk.get("confidence_score"),
            ))
        return citations
```

**Add to `.env.example` and `config.py`:**

```ini
CITATION_TEXT_MAX_CHARS=500
```

---

## 5.J — Output Verifier: Hallucination Detection & Confidence Scoring

> The Stage 4 output guard checks for grounding tokens and system prompt leaks. Stage 5
> extends this with a lightweight hallucination detector and a confidence scorer that drives
> the UI confidence badge visible to the lawyer.

### 5.J.1 Hallucination Detector

New module: `backend/app/runtime/hallucination_detector.py`

```python
class HallucinationDetector:
    """
    Lightweight, no-model hallucination signal. Does NOT require a second LLM call.

    Signal 1: Cite-but-not-retrieved check.
      Extract section references from the answer (regex: "Section \d+[A-Z]?").
      For each extracted reference, check if it appears in the retrieved chunks.
      If a cited section is NOT in any chunk, flag as UNGROUNDED_CITATION.

    Signal 2: Fabricated-act check.
      Extract Act names from the answer.
      Check against a known-acts list (loaded from data/known_acts.txt).
      If an Act name appears in the answer but not in retrieved chunks AND not in known-acts,
      flag as SUSPICIOUS_ACT.

    Signal 3: Confidence-context gap.
      If the answer is long (> 500 words) but the retrieved context is short (< 300 words),
      the model is likely extrapolating. Flag as CONTEXT_GAP.
    """
    def detect(self, answer: str, chunks: list[dict]) -> HallucinationReport:
        ...

class HallucinationReport:
    signals: list[str]             # list of fired signals
    is_flagged: bool               # True if any signal fired
    flagged_references: list[str]  # specific references that are ungrounded
```

### 5.J.2 Confidence Scorer

New module: `backend/app/runtime/confidence_scorer.py`

```python
class ConfidenceScorer:
    """
    Produces a 0.0–1.0 confidence score for the final response.
    This score is shown to the user as a badge in the UI.
    It does NOT block responses — it informs the user.

    Score components:
      - avg_trust_score of included chunks                (weight: 0.35)
      - retrieval_hit: 1.0 if chunks exist, 0.0 if none  (weight: 0.30)
      - hallucination: 1.0 - (n_signals * 0.2)           (weight: 0.20)
      - freshness: avg freshness_score of chunks          (weight: 0.15)
    """
    def score(self, answer: str, chunks: list[dict]) -> float:
        ...
```

The confidence score is included in the `done` SSE event and in the `ChatResponse` body.

**Extend `ChatResponse` schema:**

```python
class ChatResponse(BaseModel):
    answer: str
    sources: list[CitationSource]
    blocked_by: str | None
    block_reason: str | None
    confidence_score: float | None = None     # NEW
    hallucination_flags: list[str] | None = None  # NEW (empty list = clean)
```

---

## 5.K — Response Formatter

> The raw LLM output is plain text. The response formatter converts it to structured markdown
> suitable for rendering in the React chat UI and for export in Stage 6.

### 5.K.1 Formatter Module

New module: `backend/app/runtime/response_formatter.py`

```python
class ResponseFormatter:
    """
    Cleans and structures the raw LLM output.

    Steps:
    1. Strip leading/trailing whitespace.
    2. Normalize citation format: "Section 302 IPC" → "Section 302, Indian Penal Code, 1860"
       (uses known_acts.txt mapping for act name normalization)
    3. Ensure the response ends with a citation block if sources are available.
    4. Sanitize any residual prompt fragments (prompt injection defense at output layer).
    5. Return the final string — no markdown wrapping is added here; the frontend renders it.
    """
    def format(self, raw_answer: str, sources: list[CitationSource]) -> str:
        ...
```

---

## 5.L — Permanent User Knowledge (Session & Document Memory)

> User knowledge must survive logout, restart, deployment, and upgrade. This is the persistent
> memory layer for lawyers using the system across multiple sessions and matters.

### 5.L.1 User Profile and Matter Tables

New Alembic migration: `alembic/versions/XXXX_user_profile_matters.py`

```sql
-- Auto-created on first login
CREATE TABLE user_profiles (
    user_id        UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    display_name   TEXT,
    firm_name      TEXT,
    bar_council_id TEXT,
    practice_areas TEXT[],
    preferred_model VARCHAR(64),
    export_format  VARCHAR(16) DEFAULT 'pdf',
    ui_preferences JSONB DEFAULT '{}',
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);

-- One matter = one legal case or client file
CREATE TABLE user_matters (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    matter_name TEXT NOT NULL,
    matter_type VARCHAR(64),
    court       TEXT,
    case_number TEXT,
    parties     JSONB DEFAULT '[]',
    notes       TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Link existing tables to matters
ALTER TABLE session_records ADD COLUMN matter_id UUID REFERENCES user_matters(id);
ALTER TABLE chat_messages   ADD COLUMN matter_id UUID REFERENCES user_matters(id);
ALTER TABLE documents       ADD COLUMN matter_id UUID REFERENCES user_matters(id);
```

### 5.L.2 Memory Loading in chat.py

On every chat request, memory is loaded in this order:

1. **User profile** from Postgres (cached in Redis as `profile:{user_id}`, 24h TTL)
2. **Recent history** from Redis (fast path, last 5 turns)
3. **Cold-start fallback**: if Redis TTL expired, reload last 10 messages from `chat_messages`
   WHERE `matter_id = :mid ORDER BY created_at DESC LIMIT 10`
4. **Rolling summary** from `session_records.summary_text` (populated after >10 turns)

The user profile context block is prepended to every prompt (see 5.F.1, slot 2).

### 5.L.3 Memory API Routes

New file: `backend/app/routes/memory.py`

```
GET  /me/profile                     -> UserProfileResponse
PUT  /me/profile                     -> update profile
GET  /me/matters                     -> list matters (paginated)
POST /me/matters                     -> create matter
PUT  /me/matters/{matter_id}         -> update matter
GET  /me/matters/{matter_id}/history -> paginated chat messages
GET  /me/sessions                    -> all sessions, all matters (sidebar feed)
```

---

## 5.M — Environment Variables (Stage 5 Additions)

Add all of these to `.env.example` and `config.py`:

```ini
# 5.A Hardware
HARDWARE_CACHE_TTL_SECONDS=300
MODELS_DIR=./models

# 5.D Runtime
MODEL_RUNTIME=ollama               # ollama | llamacpp | transformers | mock
LLAMACPP_GPU=false
LLAMACPP_MODEL_PATH=

# 5.G Token Budget
TOKEN_BUDGET_SAFETY_MARGIN=256

# 5.I Citations
CITATION_TEXT_MAX_CHARS=500

# 5.L Memory
USER_PROFILE_CACHE_TTL=86400       # 24h Redis TTL for user profile cache
```

---

## 5.N — New Files Summary

| File | Purpose |
|------|---------|
| `backend/app/system/hardware_detector.py` | Detect CPU, RAM, GPU at startup |
| `backend/app/system/model_registry.py` | Load and query model registry |
| `backend/app/system/model_download_manager.py` | Manage model downloads |
| `backend/data/model_registry.yaml` | Registry data file |
| `backend/data/known_acts.txt` | Indian Acts reference list for hallucination detector |
| `backend/app/runtime/base.py` | `LLMRuntime` Protocol |
| `backend/app/runtime/ollama_runtime.py` | Ollama backend |
| `backend/app/runtime/llamacpp_runtime.py` | llama.cpp backend |
| `backend/app/runtime/transformers_runtime.py` | HuggingFace Transformers backend |
| `backend/app/runtime/factory.py` | Build runtime from settings |
| `backend/app/runtime/runtime_manager.py` | Singleton manager + hot-switch |
| `backend/app/runtime/context_builder.py` | Assemble prompt from parts |
| `backend/app/runtime/templates/` | Prompt template text files |
| `backend/app/runtime/token_budget_manager.py` | Fit context into token window |
| `backend/app/runtime/citation_builder.py` | Build citations from retrieved chunks |
| `backend/app/runtime/hallucination_detector.py` | Lightweight hallucination signals |
| `backend/app/runtime/confidence_scorer.py` | 0–1 confidence score for UI badge |
| `backend/app/runtime/response_formatter.py` | Clean and normalize LLM output |
| `backend/app/routes/memory.py` | Permanent user memory API |
| `alembic/versions/XXXX_user_profile_matters.py` | DB migration for profiles/matters |

---

## 5.O — Modified Files Summary

| File | What changes |
|------|-------------|
| `backend/app/routes/chat.py` | Replace `build_generator()` with `RuntimeManager.get()`. Wire `ContextBuilder`, `CitationBuilder`, `ConfidenceScorer`, `HallucinationDetector`, `ResponseFormatter`. |
| `backend/app/routes/recommend.py` | Use `ModelRegistry.recommended_for(HardwareDetector.detect())` |
| `backend/app/routes/models.py` | Use `ModelDownloadManager`. Add `/runtime/*` routes. |
| `backend/app/main.py` | Initialize `HardwareDetector` and `ModelRegistry` at startup. |
| `backend/app/schemas.py` | Add `confidence_score` and `hallucination_flags` to `ChatResponse`. |
| `backend/app/config.py` | Add all new env vars from 5.M. |

**No changes to:**
Stage 1 security isolation, Stage 2 ingestion, Stage 3 retrieval, Stage 4 defense layers.
All existing API contracts (`/chat`, `/upload`, `/recommend`, `/audit`) are preserved.

---

## 5.P — Testing Plan

All tests go in the existing `tests/` directory.

| Test file | What is tested |
|-----------|---------------|
| `tests/test_hardware_detector.py` | Profile shape, values within range |
| `tests/test_model_registry.py` | Load YAML, compatibility filter, recommendation ordering |
| `tests/test_runtime_ollama.py` | OllamaRuntime health_check, generate (mocked httpx) |
| `tests/test_runtime_llamacpp.py` | LlamaCppRuntime fallback when not installed |
| `tests/test_context_builder.py` | Priority ordering, profile block injection |
| `tests/test_token_budget.py` | Chunk trimming, minimum-1-chunk rule |
| `tests/test_citation_builder.py` | Dedup, sort by trust, text truncation |
| `tests/test_hallucination_detector.py` | Ungrounded citation signal, context gap signal |
| `tests/test_confidence_scorer.py` | Score within 0–1, weights sum to 1 |
| `tests/test_memory_api.py` | Profile CRUD, matter CRUD, history persistence after Redis TTL |

### Manual Verification Before Sign-Off

1. Change `MODEL_RUNTIME=ollama` → `MODEL_RUNTIME=mock` without restart. Confirm `/chat` still
   works. Change back. Confirm Ollama responses resume.
2. On a machine with < 8 GB RAM, confirm `GET /recommend` returns only models ≤ 4 GB RAM.
3. Pull a new model via the UI. Confirm it appears as available immediately after download
   completes with no further steps.
4. Send 12 chat messages in one session. Confirm session summary is generated for turns 1–7
   and turns 8–12 appear as history. Confirm next session loads both summary and recent history.
5. Restart the server. Reload the browser. Confirm session history is still visible
   (Postgres-backed — not lost on restart).

---

## 5.Q — Execution Order Within Stage 5

```
5.A  Hardware Detector
 ↓
5.B  Model Registry (depends on hardware for recommendation logic)
 ↓
5.C  Download Manager (depends on registry for model metadata)
 ↓
5.D  Runtime Abstraction Layer (all three backends)
 ↓
5.E  Runtime Manager + Health (depends on runtime layer)
 ↓
5.F  Context Builder + Templates
 ↓
5.G  Token Budget Manager (depends on model registry for context_window)
 ↓
5.H  Streaming Engine (wire into chat.py)
 ↓
5.I  Citation Builder
 ↓
5.J  Hallucination Detector + Confidence Scorer
 ↓
5.K  Response Formatter
 ↓
5.L  Permanent User Memory (migration + API routes)
 ↓
Wire everything into chat.py + schemas.py
 ↓
Full test suite (5.P) — sign off only when all pass
```

---

## 5.R — Hard Constraints

1. **No knowledge in the model.** All legal content lives in the retrieval layer.
2. **No training at runtime.** Model download → immediately usable. Zero post-processing.
3. **No single point of failure.** Every runtime has a fallback. Context builder returns
   empty prompt rather than crashing if profile is unavailable.
4. **No API contract changes.** `/chat`, `/upload`, `/recommend`, `/audit` are unchanged.
   New endpoints (`/runtime/*`, `/system/*`, `/me/*`) are additions only.
5. **No always-on internet required.** Hardware detection is local. Registry is a local YAML.
   Models cached locally after first download. Works fully offline.
6. **No concurrent runtime conflict.** RuntimeManager is a singleton. Switching is atomic.
