# DFrag Enterprise Architecture Audit & Permanent Remediation Plan (`isse.md`)

**Date**: 2026-09-07  
**System**: DFrag (Defensive Retrieval-Augmented Generation for Indian Law)  
**Workspace**: `c:\defensive rag\MAJOR_PROJECT`  
**Standard**: Strict Root-Cause Analysis, Senior-Level Debugging, Zero Fake Completeness, No Hardcoded Fallbacks.

---

## Executive Summary & System Diagnostic

A comprehensive audit of the live running application (accessible at `http://172.17.2.82:3000`), backend API services (`http://127.0.0.1:8000`), codebase, and phase blueprints reveals that while the UI styling and multi-layer defense abstractions are visually established, several critical core subsystems are either:
1. **Silently falling back to client-side hardcoded mock objects** (as observed in the Statute Library, Audit Ledger, and Hardware Drawer).
2. **Relying on brittle regex strings instead of enterprise models** (substituting Guardrails AI and HuggingFace classifiers with manual loops).
3. **Hardcoding legal entities and provisions** (e.g., hardcoding IPC Section 302 in the state machine, hardcoding 4 statutory acts in React).
4. **Suffering from backend attribute/import crashes** that prevent real API data from reaching the frontend.
5. **Lacking true PostgreSQL multi-user authentication and session persistence** (hardcoding `default_user` across every endpoint).

Below is the complete, line-by-line diagnosis of all defects and the exact, permanent architectural fixes required.

---

## 1. Visual & Live Interface Deficiencies (From Screenshots)

### 1.1. Hardware & AI Model Engine: CPU Stuck at "Detecting..." and Recommended Models Blank
* **Observed in Screenshot 1 & 4**:
  * The Hardware Engine drawer and view show `CPU PROCESSOR: Detecting... (x86_64 / ARM)`.
  * The `Recommended Local Models` section is completely empty.
* **Root Cause**:
  * In [frontend/src/components/HardwareForm.jsx](file:///c:/defensive%20rag/MAJOR_PROJECT/frontend/src/components/HardwareForm.jsx#L42-L68), `apiClient.getHardware()` calls `GET /system/hardware`.
  * In [backend/app/system/hardware_detector.py#L44-L52](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/system/hardware_detector.py#L44-L52), `psutil.cpu_count(logical=False)` fails or returns `None` on Windows when running under unprivileged user permissions or inside virtualized subshells, causing an unhandled exception or returning empty strings for `cpu_name`.
  * In [backend/app/routes/recommend.py#L21-L36](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/routes/recommend.py#L21-L36), `registry.recommended_for(hw)` matches models from [model_registry.yaml](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/config/model_registry.yaml). When GPU is absent (`gpu_available: false`), the filter evaluates `m.ram_required_gb <= hw.ram_available_gb`. If available RAM is calculated as 0 or if Ollama cannot be contacted at `http://127.0.0.1:11434`, an empty list is returned instead of the Tier 0 fallback list (`gemma2:2b`, `qwen2.5:3b`).
* **Permanent Fix**:
  1. In `hardware_detector.py`, harden CPU detection with multi-tier fallback: `psutil` $\rightarrow$ `platform.processor()` $\rightarrow$ Windows registry (`wmic cpu get name` or `os.environ.get('PROCESSOR_IDENTIFIER')`).
  2. In `model_registry.py`, ensure Tier 0 floor models (`gemma2:2b`, `qwen2.5:3b`) are **always returned** as guaranteed minimum baselines when VRAM is unavailable, regardless of host RAM jitter.
  3. In `HardwareForm.jsx`, if the model array is loading, display an animated skeleton loader; if Ollama is offline, display an explicit banner with a retry toggle.

---

### 1.2. Cryptographic Audit Ledger: Displaying Hardcoded Single Mock Row
* **Observed in Screenshot 3**:
  * Ledger displays `TOTAL AUDIT RECORDS: 1`, `LEGAL QUERIES EXECUTED: 1`, `SHIELD BLOCK EVENTS: 0`.
  * Row content: `session_initialized`, `System`, hash `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, prev_hash `00000000000...`.
* **Root Cause**:
  * In [frontend/src/components/AuditLedgerView.jsx#L37-L49](file:///c:/defensive%20rag/MAJOR_PROJECT/frontend/src/components/AuditLedgerView.jsx#L37-L49):
    ```javascript
    } catch (e) {
      console.warn("Audit logs fetch failed:", e);
      setLogs([{
        ts: new Date().toISOString(),
        action: 'session_initialized',
        layer: 'system',
        hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        prev_hash: '0000000000000000000000000000000000000000000000000000000000000000',
      }]);
    }
    ```
  * The backend API call `GET /audit/{session_id}` failed (or returned an empty array), triggering the hardcoded catch block!
  * In [backend/app/routes/audit.py#L24-L40](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/routes/audit.py#L24-L40), `audit_endpoint` queries `audit_logger.fetch_all()`, which queries SQLite `audit_log.db`. But on a fresh session, no session filter exists and table writes only occur when a query is submitted with the shield active.
* **Permanent Fix**:
  1. Fix the schema mismatch between SQLite `audit_log.db` and PostgreSQL `audit_events`.
  2. Implement write-through logging on **every** session creation, model switch, and network mode change so the ledger is live from turn 0.
  3. Remove the hardcoded dummy catch array in `AuditLedgerView.jsx` and replace it with an informative empty-state UI indicating: *"No events recorded yet for this session. Execute a query or toggle defense shield to view live cryptographic hashes."*

---

### 1.3. Statute Knowledge Library & Citation Graph: Completely Hardcoded Static Views
* **Observed in Screenshot 5**:
  * The Statute Library only displays 4 pre-typed acts (IT Act 2000, Companies Act 2013, BNS 2023, Contract Act 1872) with 3–4 sections each.
* **Root Cause**:
  * In [frontend/src/components/StatuteLibraryView.jsx#L14-L115](file:///c:/defensive%20rag/MAJOR_PROJECT/frontend/src/components/StatuteLibraryView.jsx#L14-L115), all statute data is hardcoded in a static constant `STATUTES_DATABASE`.
  * In [frontend/src/components/CitationGraphView.jsx#L19-L105](file:///c:/defensive%20rag/MAJOR_PROJECT/frontend/src/components/CitationGraphView.jsx#L19-L105), all nodes, relationships, and coordinates are hardcoded in `INITIAL_GRAPH_DATA`.
  * **Zero backend network calls exist in either view.**
  * In the backend, [backend/app/retrieval/pageindex.py](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/retrieval/pageindex.py) already contains the structural parser (`PageIndexBuilder.build_tree_from_text`), but **no FastAPI route exists to serve this data**.
  * In [data/acts_raw/](file:///c:/defensive%20rag/MAJOR_PROJECT/data/acts_raw/), only [IT_Act.txt](file:///c:/defensive%20rag/MAJOR_PROJECT/data/acts_raw/IT_Act.txt) exists (a 9-line snippet).
* **Permanent Fix**:
  1. Add real full-text statutory acts into `data/acts_raw/` (Bharatiya Nyaya Sanhita 2023, IT Act 2000, Companies Act 2013, Indian Contract Act 1872, Code of Criminal Procedure).
  2. Mount new REST endpoints:
     * `GET /statutes/catalog` — returns all ingested Acts, chapter counts, and section counts.
     * `GET /statutes/{act_id}/tree` — returns full hierarchical `Act -> Chapter -> Section` data parsed via `PageIndexBuilder`.
     * `GET /statutes/graph` — dynamically generates nodes and edges based on cross-statutory references and penalties extracted from ChromaDB.
  3. Rewrite `StatuteLibraryView.jsx` and `CitationGraphView.jsx` to fetch and render this dynamic backend data.

---

## 2. Critical Code-Level Bugs & Runtime Crashers

### 2.1. MCP Route & Gateway AttributeError (`settings.network_mode`)
* **Files**:
  * [backend/app/routes/mcp.py#L57](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/routes/mcp.py#L57):
    ```python
    current_network_mode = settings.network_mode.default_mode
    ```
  * [backend/app/mcp/gateway.py#L62](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/mcp/gateway.py#L62):
    ```python
    mode = (network_mode or settings.network_mode.default_mode).upper()
    ```
* **Defect**:
  * In [backend/app/config/settings.py#L121](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/config/settings.py#L121), the property is declared as:
    ```python
    network: NetworkModeConfig = Field(default_factory=NetworkModeConfig)
    ```
  * There is **no** `network_mode` attribute on `settings`.
  * Invoking `GET /mcp/status` or calling `execute_tool` immediately crashes with `AttributeError: 'Settings' object has no attribute 'network_mode'`.
* **Permanent Fix**:
  * Change `settings.network_mode.default_mode` to `settings.network.default_mode` in both `mcp.py` and `gateway.py`.
  * Add a backward-compatible `@property` in `Settings`:
    ```python
    @property
    def network_mode(self) -> NetworkModeConfig:
        return self.network
    ```

---

### 2.2. Launcher Script Database Import Crash
* **File**: [scripts/start_system.ps1#L32](file:///c:/defensive%20rag/MAJOR_PROJECT/scripts/start_system.ps1#L32)
* **Defect**:
  ```powershell
  & $VENV_PYTHON -c "from app.db.session import init_db; init_db()"
  ```
  `app.db.session` does not exist in `backend/app/db/`. The actual engine initializer is `from app.db.engine import init_db_schema`.
* **Permanent Fix**:
  Update `scripts/start_system.ps1` line 32 to:
  ```powershell
  & $VENV_PYTHON -c "import asyncio; from app.db.engine import init_db_schema; asyncio.run(init_db_schema())"
  ```

---

### 2.3. Hardcoded Tool Call Arguments in Agentic State Machine
* **File**: [backend/app/orchestrator/state_machine.py#L388-L397](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/orchestrator/state_machine.py#L388-L397)
* **Defect**:
  ```python
  res: MCPResponse = mcp_gateway.execute_tool(
      tool_name=tool_name,
      arguments={"act": "Indian Penal Code", "section": "Section 302"},
      session_id=ctx["session_id"],
      network_mode="OFFLINE"
  )
  ```
  The orchestrator passes hardcoded IPC Section 302 arguments to *every single tool*. If the planned tool is `live_statute_checker` (which requires `act_name` per its Pydantic schema), validation fails and trips the circuit breaker.
* **Permanent Fix**:
  Extract tool arguments dynamically from the user query:
  ```python
  extracted_args = self._extract_tool_arguments(tool_name, ctx["query"])
  res: MCPResponse = mcp_gateway.execute_tool(
      tool_name=tool_name,
      arguments=extracted_args,
      session_id=ctx["session_id"],
      network_mode=mode_enforcer.get_mode()
  )
  ```

---

### 2.4. Missing Grounding / Confidence Score in Chat Endpoint
* **File**: [backend/app/routes/chat.py#L129-L135](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/routes/chat.py#L129-L135)
* **Defect**:
  When `settings.orchestrator.enabled` is `True` (the default), `chat_endpoint` constructs `ChatResponse` with:
  ```python
  return ChatResponse(
      answer=orch_res.answer,
      sources=orch_res.sources,
      blocked_by=orch_res.blocked_by,
      block_reason=orch_res.block_reason
  )
  ```
  `confidence_score` and `hallucination_flags` are omitted. Consequently, the frontend's `<ConfidenceIndicator>` receives `null`, and the "Grounded (XX%)" badge never appears.
* **Permanent Fix**:
  Pass `confidence_score=orch_res.budget_snapshot.get("confidence", 1.0)` and `hallucination_flags` into `ChatResponse`.

---

## 3. Replacement of Brittle Regex / Patterns with Real Models

### 3.1. Output Guard: Integrating Guardrails AI
* **Current State**: [backend/app/security/output_validator.py](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/security/output_validator.py) uses manual Python word-intersection math and docstrings falsely claiming to be a "Guardrails Schema".
* **Permanent Fix**:
  1. Utilize the installed `guardrails-ai` library.
  2. Implement an official local guardrail specification using `guardrails.Guard.from_pydantic()`:
     ```python
     from guardrails import Guard
     from guardrails.hub import ProvenanceEmbeddings, CompetitorCheck
     ```
  3. Use Guardrails to strictly validate:
     * Structured JSON / Markdown response format.
     * Provenance grounding: verifying that every statement maps to an extracted statutory text span.
     * Elimination of hallucinated section numbers.

---

### 3.2. Injection Guard: Integrating Transformer Classifier (ProtectAI / Prompt Guard)
* **Current State**: [backend/app/security/injection_gate.py](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/security/injection_gate.py) contains an 85-item regex list. Any slightly rephrased jailbreak or obfuscated input bypasses regex.
* **Permanent Fix**:
  1. Implement a 2-stage hybrid gate:
     * **Stage 1 (Fast Deterministic Pass)**: Rejects obvious SQLi and shell characters in $< 1\text{ ms}$.
     * **Stage 2 (Local Small Transformer Classifier)**: Load an 86M–110M parameter ONNX/HuggingFace model (such as `protectai/deberta-v3-base-prompt-injection` or `meta-llama/Prompt-Guard-86M`) running on CPU/ONNX Runtime.
  2. Evaluates semantic injection probability with zero external network calls.
  3. Replaces brittle regex matching with true adversarial robustness.

---

### 3.3. Legal Domain Embeddings: `InLegalBERT`
* **Current State**: [backend/app/retrieval/tier1_law.py](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/retrieval/tier1_law.py) falls back to generic Chroma ONNX embeddings, which have no understanding of Indian legal terminology (e.g. *mens rea*, *fir*, *suo motu*, *habeas corpus*).
* **Permanent Fix**:
  1. Explicitly wire `law-ai/InLegalBERT` or `BAAI/bge-small-en` via HuggingFace SentenceTransformers in `client.py`.
  2. Pre-generate and serialize dense vector embeddings for the statutory corpus using an offline seeding script.

---

## 4. PostgreSQL Long-Term Context, Authentication & Multi-Tenant Isolation

### 4.1. The Missing User Authentication & Account Architecture
* **Current State**:
  * Every endpoint in `chat.py`, `upload.py`, and `state_machine.py` uses `user_id="default_user"`.
  * The frontend displays a hardcoded profile: `{ username: 'Dinol Castelino', email: 'dinol@dfrag.ai' }`.
  * No `User` ORM model exists in [backend/app/db/models.py](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/db/models.py).
* **Permanent Fix**:
  1. **Add `User` Model in `app/db/models.py`**:
     ```python
     class User(Base):
         __tablename__ = "users"
         id = Column(String(64), primary_key=True)
         username = Column(String(64), unique=True, index=True)
         email = Column(String(128), unique=True, index=True)
         hashed_password = Column(String(255), nullable=False)
         created_at = Column(DateTime, default=datetime.utcnow)
     ```
  2. **Add JWT Authentication Layer**:
     * Implement `POST /auth/register` and `POST /auth/login`.
     * Attach FastAPI dependency `get_current_user` to `/chat`, `/upload`, and `/memory`.
  3. **Multi-Session History & Long-Term Context**:
     * Store conversations permanently associated with `user.id`.
     * When the user logs in, populate the sidebar with their real conversation threads.
     * Maintain L3 Semantic Memory (facts, client preferences, firm profile) across all historical sessions.

---

### 4.2. Hardcoded Database Credentials
* **File**: [backend/app/config/settings.py#L53](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/config/settings.py#L53)
* **Defect**: Contains hardcoded credentials: `postgresql+psycopg://postgres:dinolino77@127.0.0.1:5432/dfrag`.
* **Permanent Fix**:
  Remove the hardcoded password and read exclusively from environment variables:
  ```python
  postgres_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:@127.0.0.1:5432/dfrag"))
  ```

---

## 5. Automated Hardware Detection & Zero-Terminal Model Adaptation

You emphasized: *End users must never run terminal commands or manually execute `ollama pull`.*

### Permanent Architecture:
1. **On App Startup (Browser Load)**:
   * Frontend calls `GET /models/auto-select`.
   * Backend inspects host CPU, RAM, and GPU VRAM.
   * Backend queries Ollama (`GET http://127.0.0.1:11434/api/tags`) to inspect installed models.
2. **Automated Dynamic Model Ingestion**:
   * If the host has no legal models installed:
     * **Tier 0 PC ($< 8\text{ GB}$ RAM / No GPU)** $\rightarrow$ Backend triggers background HTTP download of `gemma2:2b`.
     * **Tier 1 PC ($8 – 16\text{ GB}$ RAM / 4GB+ VRAM)** $\rightarrow$ Backend triggers background HTTP download of `qwen2.5:7b`.
     * **Tier 2 PC ($> 16\text{ GB}$ RAM / Dedicated 12GB+ GPU)** $\rightarrow$ Backend triggers background HTTP download of `qwen2.5:14b`.
3. **Automated Modelfile Adaptation**:
   * As soon as the base model is pulled, the backend programmatically executes Ollama's Create API (`POST /api/create`):
     ```json
     {
       "name": "dfrag-legal:latest",
       "modelfile": "FROM qwen2.5:7b\nSYSTEM \"You are DFrag Enterprise Legal Assistant. Ground all answers strictly in Indian statutory context and cite sections.\"\nPARAMETER temperature 0.1\nPARAMETER top_p 0.9"
     }
     ```
   * **Result**: The legal model is built, adapted, and mounted **without the user ever touching a terminal, VS Code, or CLI**.

---

## 6. Docker & Containerization Standardization

### 6.1. Missing Ollama Service in `docker-compose.yml`
* **Defect**: [docker-compose.yml](file:///c:/defensive%20rag/MAJOR_PROJECT/docker-compose.yml) lacks an `ollama` container, assuming Ollama is pre-installed on the host.
* **Permanent Fix**:
  Add a dedicated Ollama container service with optional NVIDIA GPU passthrough:
  ```yaml
  services:
    ollama:
      image: ollama/ollama:latest
      container_name: dfrag-ollama
      ports:
        - "11434:11434"
      volumes:
        - ollama-models:/root/.ollama
      restart: always
      deploy:
        resources:
          reservations:
            devices:
              - driver: nvidia
                count: all
                capabilities: [gpu]
  ```

---

### 6.2. Ingestion Security Bypass in `upload.py`
* **Defect**: [backend/app/routes/upload.py](file:///c:/defensive%20rag/MAJOR_PROJECT/backend/app/routes/upload.py) imports `PDFExtractor` and skips `PDFSanitizer`.
* **Permanent Fix**:
  Replace `PDFExtractor` in `upload.py` with `PDFSanitizer`:
  ```python
  from app.security.pdf_sanitizer import pdf_sanitizer

  # Inside upload_endpoint
  text, metadata = pdf_sanitizer.extract_clean_text(content)
  chunks_added = tier2_retriever.add_documents(session_id, file.filename, text)
  ```
  This immediately activates magic bytes verification, executable script blocking, and page quota enforcement on all uploads.

---

## 7. Master Remediation Roadmap

```
[PHASE A: Core Crash & Runtime Fixes]
 ├── Fix settings.network_mode attribute in mcp.py & gateway.py
 ├── Fix app.db.session import in scripts/start_system.ps1
 ├── Pass confidence_score in chat.py orchestrator response
 └── Secure database credentials (remove cleartext dinolino77)

[PHASE B: Dynamic Models & Defense Modernization]
 ├── Replace regex-only injection gate with local ONNX transformer classifier
 ├── Integrate real Guardrails-AI schema and provenance validation
 ├── Wire InLegalBERT / BGE embeddings into Tier 1 and Tier 2 retrieval
 └── Fix CPU detection and model recommendations in HardwareForm

[PHASE C: Dynamic Legal Knowledge & PageIndex Tree API]
 ├── Mount GET /statutes/catalog, GET /statutes/{id}/tree, and GET /statutes/graph
 ├── Replace hardcoded STATUTES_DATABASE in StatuteLibraryView.jsx
 ├── Replace hardcoded INITIAL_GRAPH_DATA in CitationGraphView.jsx
 └── Seed data/acts_raw/ with authentic BNS 2023, IT Act, Companies Act, Contract Act

[PHASE D: PostgreSQL User Auth & Long-Term Memory]
 ├── Create User model and password hashing in app/db/models.py
 ├── Implement JWT register/login endpoints and auth dependency
 └── Tie conversations and semantic memory to authenticated user IDs

[PHASE E: Automated Deployment & Docker Architecture]
 ├── Add managed Ollama service to docker-compose.yml
 ├── Download spaCy en_core_web_sm in backend/Dockerfile
 └── Wire pdf_sanitizer into upload.py for magic-byte verification
```

---

## Conclusion

This file serves as the definitive reference for fixing all identified bugs, eliminating hardcoded components, and transitioning DFrag into a production-grade enterprise legal AI workspace. Every issue listed above has been traced to its specific line numbers and has an exact remediation path.
