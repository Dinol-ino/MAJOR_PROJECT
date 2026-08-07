# Stage 7 — Enterprise Knowledge Ecosystem

> **This stage builds the knowledge management platform that sits beneath the runtime.**
> Stage 5 built the runtime intelligence. Stage 6 made it deployable. Stage 7 makes the
> knowledge base live, authoritative, and automatically synchronized with the real world.
>
> **Core principle:** The LLM is a reasoning engine. This stage ensures it always reasons
> from current, verified, deduplicated, versioned knowledge — regardless of whether the
> law changed yesterday or the user uploaded a new document this morning.
>
> **Prerequisite:** Stages 1–6 stable. Stage 5 runtime abstraction in place. Stage 2/3
> ingestion pipeline operational. All `tests/` passing.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│              STAGE 7 — KNOWLEDGE ECOSYSTEM                           │
│                                                                      │
│  External Sources                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ India    │ │ e-Gazette│ │ SC/HC    │ │ Legal    │ │ User     │ │
│  │ Code     │ │ RSS/API  │ │ Judgments│ │ APIs     │ │ Uploads  │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │
│       │            │            │            │            │         │
│  ┌────▼────────────▼────────────▼────────────▼────────────▼──────┐  │
│  │                    CONNECTOR LAYER (7.A)                       │  │
│  │  IndiaCodeConnector │ GazetteConnector │ SCJudgmentConnector  │  │
│  │  IndianKanoonConnector │ RSSConnector │ UserUploadConnector   │  │
│  └────────────────────────────┬──────────────────────────────────┘  │
│                               │ raw document + metadata             │
│  ┌────────────────────────────▼──────────────────────────────────┐  │
│  │                  INGESTION PIPELINE (7.B)                     │  │
│  │  Authentication → Validation → Parser → Normalizer →          │  │
│  │  Metadata Extraction → Deduplication → Version Control →      │  │
│  │  Chunking → Embedding → Knowledge Store                       │  │
│  └────────────────────────────┬──────────────────────────────────┘  │
│                               │                                     │
│  ┌────────────────────────────▼──────────────────────────────────┐  │
│  │                  KNOWLEDGE STORE (7.C)                        │  │
│  │  pgvector (primary)  │  ChromaDB (fallback)  │  BM25 index   │  │
│  │  Document version table  │  Chunk table  │  Audit trail      │  │
│  └────────────────────────────┬──────────────────────────────────┘  │
│                               │                                     │
│  ┌────────────────────────────▼──────────────────────────────────┐  │
│  │                SYNC SERVICE (7.D)                             │  │
│  │  Change detection │ Diff computation │ Incremental re-embed  │  │
│  │  Cache invalidation │ Index refresh                          │  │
│  └────────────────────────────┬──────────────────────────────────┘  │
│                               │                                     │
│  ┌────────────────────────────▼──────────────────────────────────┐  │
│  │         RETRIEVER (Stage 3, unchanged interface)              │  │
│  │         Stage 5 Runtime reads from here                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 7.A — Connector Architecture

> Every external source has a dedicated connector. Every connector implements the same
> interface. No connector is ever allowed to write directly to the vector database.
> All connectors produce raw documents that enter the ingestion pipeline at the top.

### 7.A.1 Connector Interface

New module: `backend/app/knowledge/connectors/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class RawDocument:
    """
    The output of every connector. Standardized envelope for any source.
    """
    source_id: str           # unique within the connector namespace
    source_type: str         # "india_code" | "gazette" | "sc_judgment" | "rss" | "user_upload"
    title: str
    content: str             # raw text (UTF-8)
    url: str | None          # canonical URL for this document
    published_at: datetime | None
    retrieved_at: datetime
    language: str            # "en" | "hi" | "te" | ...
    raw_metadata: dict       # connector-specific key-value pairs (Act name, year, etc.)

class BaseConnector(ABC):
    """
    Every connector must implement exactly these three methods.
    """

    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Verify that the connector's credentials are valid and the source is reachable.
        Called at startup and before every scheduled sync.
        """
        ...

    @abstractmethod
    async def fetch(self, since: datetime | None = None) -> list[RawDocument]:
        """
        Fetch documents from the source.
        If `since` is provided, return only documents newer than that timestamp.
        If `since` is None, perform a full fetch (first-time ingestion).
        """
        ...

    @abstractmethod
    def source_type(self) -> str:
        """Return the connector's source_type string."""
        ...
```

### 7.A.2 Connector Implementations

New directory: `backend/app/knowledge/connectors/`

```
connectors/
  base.py                      # BaseConnector, RawDocument
  india_code.py                # IndiaCodeConnector
  gazette.py                   # GazetteConnector (RSS + API)
  sc_judgment.py               # SCJudgmentConnector (public SC website)
  indian_kanoon.py             # IndianKanoonConnector (API, requires key)
  rss.py                       # GenericRSSConnector (Bar & Bench, LiveLaw, PIB)
  user_upload.py               # UserUploadConnector (already partially exists in upload.py)
  registry.py                  # ConnectorRegistry — maps source_type to class
```

#### IndiaCodeConnector

```python
class IndiaCodeConnector(BaseConnector):
    """
    Fetches Central Acts from the India Code API (indiacode.nic.in).
    India Code exposes a RESTful API with XML/JSON responses.
    Rate limit: 1 request per second. Implements exponential backoff.

    Full ingestion: all Central Acts, Amendments, Rules.
    Incremental: checks Last-Modified headers. Only fetches changed Acts.
    """
    BASE_URL = "https://www.indiacode.nic.in"

    async def authenticate(self) -> bool:
        # India Code is unauthenticated for public acts
        # INDIA_CODE_API_KEY env var enables higher rate limits if available
        return True

    async def fetch(self, since: datetime | None = None) -> list[RawDocument]:
        # GET /api/v1/acts?modified_after={since.isoformat()} if since is set
        # Returns list of Act JSONs; for each, fetch full text via /api/v1/acts/{id}/text
        # Produces one RawDocument per Act section (not per Act)
        ...
```

#### GazetteConnector

```python
class GazetteConnector(BaseConnector):
    """
    Fetches Gazette of India notifications from egazette.nic.in.
    Primary method: RSS feed (https://egazette.nic.in/rss/gazette.rss)
    Fallback: direct website scraping if RSS is unavailable.

    Gazette notifications are the authoritative source for:
    - New Acts receiving Presidential assent
    - Statutory Rules and Orders
    - Government notifications
    """
    ...
```

#### SCJudgmentConnector

```python
class SCJudgmentConnector(BaseConnector):
    """
    Fetches recent Supreme Court judgments from the public SC website
    (main.sci.gov.in). Only fetches judgments marked as publicly available.
    Uses the SC's existing PDF download API where available.
    Falls back to the Indian Kanoon API for structured judgment data.
    """
    ...
```

#### GenericRSSConnector

```python
class GenericRSSConnector(BaseConnector):
    """
    Configurable RSS connector. A single instance handles multiple feeds.
    Feed list loaded from MCP_RSS_FEEDS env var (comma-separated URLs).
    Supported feeds: PIB, Bar & Bench, LiveLaw, Indian Express Legal.

    Trust score for RSS content: 0.65 (lower than primary corpus).
    RSS content is tagged source_type='live_news' and rendered distinctly in the UI.
    """
    ...
```

### 7.A.3 Connector Registry

New module: `backend/app/knowledge/connectors/registry.py`

```python
CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
    "india_code":     IndiaCodeConnector,
    "gazette":        GazetteConnector,
    "sc_judgment":    SCJudgmentConnector,
    "indian_kanoon":  IndianKanoonConnector,
    "rss":            GenericRSSConnector,
    "user_upload":    UserUploadConnector,
}

def get_connector(source_type: str, **kwargs) -> BaseConnector:
    cls = CONNECTOR_REGISTRY.get(source_type)
    if not cls:
        raise ValueError(f"Unknown connector: {source_type}")
    return cls(**kwargs)
```

### 7.A.4 Adding a New Connector

To add a new connector (e.g., a state High Court feed or a private legal API):

1. Create `backend/app/knowledge/connectors/my_source.py` implementing `BaseConnector`.
2. Register it in `CONNECTOR_REGISTRY`.
3. Add its `source_type` and any required API keys to `.env.example` and `config.py`.
4. Add a `ConnectorConfig` row to the database via the admin API.
5. The sync service picks it up on the next scheduled run. No other changes required.

---

## 7.B — Ingestion Pipeline

> Every document from every connector passes through the same pipeline. The pipeline is
> immutable — no connector can skip a stage. This ensures knowledge quality, deduplication,
> versioning, and audit integrity across all sources.

### 7.B.1 Pipeline Stages

```
RawDocument (from connector)
    │
    ▼
1. Authentication Guard
   Verifies the document originated from a registered, authenticated connector.
   Rejects documents from unknown sources.
    │
    ▼
2. Validation
   Schema validation: required fields present (title, content, source_id, published_at).
   Content validation: not empty, not binary garbage, language detection.
   Size validation: content within MAX_DOCUMENT_SIZE_CHARS (configurable).
   Rejects malformed documents with a detailed error in the ingestion log.
    │
    ▼
3. Parser
   Converts raw content to clean plaintext.
   Handles: PDF (pdfplumber + PyMuPDF), DOCX (python-docx), HTML (BeautifulSoup),
            plaintext, XML (India Code API format).
   Preserves structural hints: section headings, numbered lists.
    │
    ▼
4. Normalizer
   Unicode normalization (NFC).
   Remove control characters, non-printable characters.
   Normalize whitespace.
   Normalize Act name aliases: "IPC" → "Indian Penal Code, 1860".
   Language detection and tagging.
    │
    ▼
5. Metadata Extraction
   Extract: Act name, Section numbers, Year, Court name, Case number.
   Detect document type: statute | judgment | gazette | news | user_document.
   Assign trust_tier based on source_type:
     india_code / gazette → tier_1 (trust_score = 1.0)
     sc_judgment          → tier_1 (trust_score = 0.95)
     indian_kanoon        → tier_1 (trust_score = 0.90)
     rss                  → tier_3 (trust_score = 0.65)
     user_upload          → tier_2 (trust_score = 0.80, workspace-scoped)
    │
    ▼
6. Deduplication
   Compute a content fingerprint: uuid5(namespace=source_type, name=sha256(content)).
   Check against the `documents` table.
   If fingerprint exists and content hash is identical: skip (already ingested).
   If fingerprint exists and content hash differs: proceed as a new version (see 7.C.2).
   If fingerprint not found: proceed as new document.
    │
    ▼
7. Version Control
   Every document has a version history.
   A new version is created when: content changes, metadata changes, or the source
   explicitly signals a supersession (e.g., a new Gazette notification repeals an old one).
   Previous versions are retained and queryable.
   Only the latest active version participates in retrieval.
    │
    ▼
8. Chunking
   Route to the appropriate chunker based on doc_type:
     statute / act / rule → LegalChunker (section-boundary splitting)
     judgment / order     → ParagraphChunker (paragraph-boundary splitting)
     gazette / news       → SlidingWindowChunker (512 tokens, 128 overlap)
     user_upload          → auto-detected doc_type, then appropriate chunker
   Each chunk inherits all metadata from its parent document.
   Each chunk is assigned: chunk_index, page_number (if available), char_offset.
    │
    ▼
9. Embedding
   Embed each chunk using the configured embedding model.
   Default: jinaai/jina-embeddings-v3 (1024-dim).
   Embedding is async and batched (batch_size=32, configurable).
   On embedding failure: retry 3 times, then mark chunk as pending_embed.
   A background job retries pending_embed chunks on the next sync cycle.
    │
    ▼
10. Knowledge Store Write
    Write to pgvector primary store (chunk text + embedding + metadata).
    Write to ChromaDB legacy store if CHROMA_LEGACY_ENABLED=true.
    Update BM25 index (in-memory rebuild triggered by sync service).
    Update document version table.
    Emit ingestion event to audit log.
```

### 7.B.2 Ingestion Pipeline Module

New module: `backend/app/knowledge/ingestion_pipeline.py`

```python
class IngestionPipeline:
    """
    The single entry point for all document ingestion.
    Called by the sync service (scheduled) and by the upload endpoint (on-demand).
    """

    async def ingest(self, raw: RawDocument) -> IngestionResult:
        try:
            validated = await self._validate(raw)
            parsed    = await self._parse(validated)
            normalized = self._normalize(parsed)
            metadata  = self._extract_metadata(normalized)
            dedup     = await self._deduplicate(metadata)
            if dedup.is_exact_duplicate:
                return IngestionResult(status="skipped", reason="duplicate")
            versioned = await self._version(dedup)
            chunks    = self._chunk(versioned)
            embedded  = await self._embed(chunks)
            await self._store(embedded)
            return IngestionResult(status="ingested", chunks_written=len(embedded))
        except IngestionValidationError as e:
            await self._log_failure(raw, e)
            return IngestionResult(status="rejected", reason=str(e))
        except Exception as e:
            await self._log_failure(raw, e)
            return IngestionResult(status="error", reason=str(e))

    async def ingest_batch(self, docs: list[RawDocument]) -> list[IngestionResult]:
        return [await self.ingest(doc) for doc in docs]
```

### 7.B.3 Legal Chunker

New module: `backend/app/knowledge/chunkers/legal_chunker.py`

```python
import re

class LegalChunker:
    """
    Splits Indian statutes at section boundaries.
    A section is the atomic unit of Indian legislation — it must never be split mid-section.
    """
    SECTION_PATTERN = re.compile(
        r'^(?:Section|Sec\.|Art(?:icle)?\.?)\s*\d+[A-Z]?\.?\s',
        re.MULTILINE | re.IGNORECASE
    )

    def chunk(self, text: str, metadata: dict) -> list[Chunk]:
        boundaries = [m.start() for m in self.SECTION_PATTERN.finditer(text)]
        if len(boundaries) < 2:
            # Not a statute or single-section document — fall through to paragraph chunker
            return ParagraphChunker().chunk(text, metadata)
        # Split at section boundaries; each split = one chunk
        sections = []
        for i, start in enumerate(boundaries):
            end = boundaries[i + 1] if i + 1 < len(boundaries) else len(text)
            section_text = text[start:end].strip()
            if len(section_text) > settings.CHUNK_MIN_CHARS:
                sections.append(Chunk(text=section_text, metadata=metadata, chunk_index=i))
        return sections
```

---

## 7.C — Knowledge Store

> The knowledge store is the single authoritative data layer for all ingested knowledge.
> It has two concerns: the document catalog (metadata + versioning) and the vector store
> (embeddings for retrieval). Both live in Postgres.

### 7.C.1 New Database Tables

New Alembic migration: `alembic/versions/XXXX_knowledge_store.py`

```sql
-- Document catalog: one row per unique document (all versions)
CREATE TABLE knowledge_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type     VARCHAR(64) NOT NULL,
    source_id       TEXT NOT NULL,           -- connector-specific unique ID
    content_hash    TEXT NOT NULL,           -- sha256 of normalized content
    fingerprint     UUID NOT NULL,           -- uuid5 for dedup
    title           TEXT,
    url             TEXT,
    published_at    TIMESTAMPTZ,
    ingested_at     TIMESTAMPTZ DEFAULT now(),
    doc_type        VARCHAR(64),             -- statute | judgment | gazette | news | user_document
    trust_tier      VARCHAR(16),             -- tier_1 | tier_2 | tier_3
    trust_score     FLOAT,
    language        VARCHAR(8) DEFAULT 'en',
    act_name        TEXT,
    is_active       BOOLEAN DEFAULT TRUE,    -- only active docs participate in retrieval
    workspace_id    UUID,                    -- NULL for public corpus; UUID for user-uploaded
    UNIQUE (source_type, source_id, content_hash)
);

-- Version history: one row per version of each document
CREATE TABLE knowledge_document_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES knowledge_documents(id),
    version_number  INTEGER NOT NULL,
    content_hash    TEXT NOT NULL,
    ingested_at     TIMESTAMPTZ DEFAULT now(),
    is_current      BOOLEAN DEFAULT TRUE,
    supersedes_id   UUID REFERENCES knowledge_document_versions(id)
);

-- Chunks: one row per chunk per active document version
CREATE TABLE knowledge_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES knowledge_documents(id),
    version_id      UUID NOT NULL REFERENCES knowledge_document_versions(id),
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    section         TEXT,
    page_number     INTEGER,
    char_offset     INTEGER,
    embedding       vector(1024),            -- pgvector column
    trust_score     FLOAT,
    freshness_score FLOAT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX knowledge_chunks_embedding_idx ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX knowledge_chunks_document_idx ON knowledge_chunks (document_id);
CREATE INDEX knowledge_chunks_active_idx ON knowledge_chunks (is_active) WHERE is_active = TRUE;
CREATE INDEX knowledge_chunks_workspace_idx ON knowledge_chunks (document_id);
```

### 7.C.2 Version Control Logic

When a document is updated (content hash changes):

1. Set the old `knowledge_document_versions.is_current = FALSE`.
2. Insert a new version row with `is_current = TRUE`, `version_number += 1`.
3. Set old chunks' `is_active = FALSE`.
4. Ingest new chunks with `is_active = TRUE`.
5. The retriever only queries `WHERE is_active = TRUE` — old chunks are automatically excluded.
6. Old versions remain in the database for audit and rollback.

To roll back to a previous version: set the old version's `is_current = TRUE` and
set its chunks' `is_active = TRUE`. Set the current version's values to FALSE.

### 7.C.3 Knowledge Store API

```
GET  /knowledge/stats           -> document counts by source_type and tier
GET  /knowledge/documents       -> list documents (paginated, filterable by source_type)
GET  /knowledge/documents/{id}  -> single document metadata + version history
GET  /knowledge/documents/{id}/versions -> all versions
POST /knowledge/documents/{id}/rollback -> rollback to a previous version (admin only)
DELETE /knowledge/documents/{id} -> soft delete (sets is_active=FALSE on doc + chunks)
```

---

## 7.D — Live Knowledge Synchronization Service

> The sync service keeps the knowledge base current without human intervention. It runs
> on a schedule, detects changes, and only re-ingests what has changed. The LLM benefits
> from updated knowledge immediately — with no restart, no model change, no retraining.

### 7.D.1 Sync Service Architecture

New module: `backend/app/knowledge/sync_service.py`

```python
class KnowledgeSyncService:
    """
    Background service. Runs on SYNC_SCHEDULE cron.
    For each enabled connector, fetches documents since last_sync_at,
    runs them through the ingestion pipeline, then updates last_sync_at.

    Does NOT run at startup to avoid blocking application launch.
    First sync is scheduled SYNC_INITIAL_DELAY_MINUTES after startup.
    """

    async def run_sync(self, source_type: str | None = None) -> SyncReport:
        """
        Run sync for one source_type (or all if None).
        Returns a SyncReport with counts: fetched, ingested, skipped, errors.
        """
        sources = [source_type] if source_type else self._enabled_sources()
        results = []
        for src in sources:
            connector = get_connector(src)
            authenticated = await connector.authenticate()
            if not authenticated:
                results.append(SyncResult(source=src, status="auth_failed"))
                continue
            last_sync = await self._get_last_sync(src)
            docs = await connector.fetch(since=last_sync)
            batch_results = await self.pipeline.ingest_batch(docs)
            await self._set_last_sync(src, datetime.utcnow())
            await self._invalidate_caches(src)
            results.append(SyncResult(source=src, results=batch_results))
        return SyncReport(results=results, completed_at=datetime.utcnow())

    async def _invalidate_caches(self, source_type: str) -> None:
        """
        After any ingestion: flush relevant Redis cache keys.
        Chat response cache keys for queries containing terms from the updated source.
        The next query will get fresh retrieval results.
        """
        # Pattern-based Redis key deletion: "dfrag:chat_cache:*"
        # Only flush if new chunks were actually written (avoid unnecessary invalidation)
        ...
```

### 7.D.2 Change Detection & Diff

```python
class ChangeDetector:
    """
    Compares a newly fetched document against the stored version.
    Returns a ChangeReport indicating what changed.
    """

    def detect(self, incoming: RawDocument, stored: KnowledgeDocument) -> ChangeReport:
        incoming_hash = sha256(incoming.content.encode()).hexdigest()
        if incoming_hash == stored.content_hash:
            return ChangeReport(changed=False)

        # Content has changed — compute a structural diff
        changes = self._compute_diff(stored.content, incoming.content)
        return ChangeReport(
            changed=True,
            sections_added=changes.added,
            sections_removed=changes.removed,
            sections_modified=changes.modified,
            is_major_change=len(changes.removed) > 0,  # removals = substantive change
        )

    def _compute_diff(self, old: str, new: str) -> DiffResult:
        # difflib.unified_diff at section level (using LegalChunker boundaries)
        # Returns section-level diff, not character-level diff
        ...
```

Only changed sections are re-chunked and re-embedded. Unchanged sections retain their
existing embeddings. This is the correct incremental update strategy.

### 7.D.3 Sync Schedule Configuration

```ini
# Sync schedules (cron format)
SYNC_INDIA_CODE_SCHEDULE=0 2 * * 0          # weekly, Sunday 2am
SYNC_GAZETTE_SCHEDULE=0 */6 * * *           # every 6 hours
SYNC_SC_JUDGMENTS_SCHEDULE=0 8 * * *        # daily at 8am
SYNC_RSS_SCHEDULE=*/30 * * * *              # every 30 minutes
SYNC_INITIAL_DELAY_MINUTES=5               # delay after startup before first sync
```

### 7.D.4 Sync Admin API

```
GET  /admin/sync/status                -> last sync time per source, next scheduled sync
POST /admin/sync/run                   -> trigger immediate sync (all or specific source)
POST /admin/sync/run/{source_type}     -> trigger sync for one source
GET  /admin/sync/history               -> paginated sync run history with counts
GET  /admin/sync/errors                -> documents that failed ingestion (last 100)
```

---

## 7.E — User Knowledge: Permanent Storage

> User-uploaded documents, conversation summaries, and matter memory must survive every
> operational event: logout, restart, deployment, upgrade. This is the guarantee to the
> practicing lawyer.

### 7.E.1 What Persists

| Data | Storage | Survives |
|------|---------|---------|
| User profile (firm, BCI ID, practice areas) | Postgres `user_profiles` | Everything |
| Matters (case name, court, parties) | Postgres `user_matters` | Everything |
| Chat messages (full text + sources) | Postgres `chat_messages` | Everything |
| Session summaries (rolling summary of older turns) | Postgres `session_records.summary_text` | Everything |
| Uploaded documents (text + embeddings) | Postgres `knowledge_chunks` (workspace-scoped) | Everything |
| Recent conversation context | Redis (2h TTL) | Redis restart only — Postgres fallback |

### 7.E.2 Separation of Session Memory and Document Memory

These are distinct and must not be conflated:

**Session memory**: the conversation turns for the current matter. Stored in `chat_messages`,
cached in Redis. Loaded into the context builder as conversation history (Stage 5.F).

**Document memory**: the user's uploaded PDFs, Word documents, and scraped content. Stored
as chunks in `knowledge_chunks` with `workspace_id` set. Retrieved by the vector retriever
(Stage 3) alongside the public corpus. Documents survive indefinitely — they are not
tied to any session.

A lawyer uploads a client brief once. It remains retrievable in every future session for that
matter, for the lifetime of the account.

### 7.E.3 User Knowledge API

Extends the `memory.py` routes from Stage 5:

```
GET  /me/documents                       -> list all uploaded documents
GET  /me/documents/{id}                  -> document metadata + chunk count
DELETE /me/documents/{id}                -> soft delete (sets is_active=FALSE)
GET  /me/matters/{id}/documents          -> documents linked to a specific matter
GET  /me/matters/{id}/history            -> full chat history for a matter
POST /me/matters/{id}/export             -> export all chat history to PDF/DOCX (Stage 5 export)
```

---

## 7.F — Connector Configuration Management

> Connectors are configured through the admin interface. No code change is required to
> enable, disable, or modify a connector's schedule or credentials.

### 7.F.1 Connector Config Table

```sql
CREATE TABLE connector_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type     VARCHAR(64) NOT NULL UNIQUE,
    enabled         BOOLEAN DEFAULT TRUE,
    schedule        TEXT,                   -- cron expression
    credentials     JSONB DEFAULT '{}',     -- encrypted at rest
    last_sync_at    TIMESTAMPTZ,
    last_sync_status VARCHAR(32),
    error_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

Credentials in the `credentials` JSONB column are encrypted using `CONNECTOR_ENCRYPTION_KEY`
(AES-256-GCM). The key is stored as an environment variable, never in the database.

### 7.F.2 Connector Admin API

```
GET  /admin/connectors              -> list all connectors with status
PUT  /admin/connectors/{type}       -> update schedule, credentials, enabled flag
POST /admin/connectors/{type}/test  -> test authentication for one connector
GET  /admin/connectors/{type}/logs  -> last 100 sync events for one connector
```

---

## 7.G — Trust Tier System

> Every chunk in the knowledge store has a trust score. The trust score is used by Stage 4's
> TrustScorer, Stage 5's ConfidenceScorer, and the UI citation panel. Stage 7 formalizes
> the trust tier assignment across all sources.

### 7.G.1 Trust Tier Assignment

| Source | Trust Tier | Trust Score | Rationale |
|--------|-----------|-------------|-----------|
| India Code (indiacode.nic.in) | Tier 1 | 1.00 | Government primary source |
| e-Gazette (egazette.nic.in) | Tier 1 | 1.00 | Official Government of India gazette |
| Supreme Court (main.sci.gov.in) | Tier 1 | 0.95 | Authoritative court |
| Indian Kanoon API | Tier 1 | 0.90 | Verified legal repository |
| High Court (state-specific) | Tier 1 | 0.90 | Authoritative court |
| User Uploads (enterprise docs) | Tier 2 | 0.80 | Workspace-scoped, user-verified |
| HuggingFace datasets | Tier 2 | 0.75 | Pre-processed, not primary source |
| RSS Legal News (Bar & Bench) | Tier 3 | 0.65 | Journalistic, not primary source |
| PIB Press Releases | Tier 3 | 0.70 | Government communication, not gazette |

### 7.G.2 Trust Score Usage in Retrieval

When the retriever returns chunks, they are sorted by a composite score:

```
composite_score = (
    0.4 * similarity_score +        # vector similarity to query
    0.3 * trust_score +             # source trust tier
    0.2 * freshness_score +         # recency (newer = higher)
    0.1 * (1 - injection_risk_score) # injection safety
)
```

This is the same formula used in Stage 4's TrustScorer. Stage 7 extends it to cover the
new source types added by the connector architecture.

---

## 7.H — Freshness Scoring

> An Act from 1860 with no amendments since 2020 is less fresh than a Gazette notification
> from last week. Freshness affects trust and retrieval ranking.

### 7.H.1 Freshness Score Computation

```python
def compute_freshness_score(published_at: datetime | None, doc_type: str) -> float:
    """
    Returns a 0.0–1.0 freshness score.

    Freshness decay is logarithmic, not linear.
    Recent content decays slowly (small day differences = small score drop).
    Old content stabilizes at a floor (old statutes don't become untrustworthy).
    """
    if published_at is None:
        return 0.5  # unknown date: neutral

    age_days = (datetime.utcnow() - published_at).days

    if doc_type in ("gazette", "rss"):
        # News/notifications decay quickly — 30 days old = 0.7 freshness
        return max(0.2, 1.0 - (age_days / 150))

    if doc_type in ("judgment",):
        # Judgments decay moderately — 1 year old = 0.8 freshness
        return max(0.5, 1.0 - (age_days / 1825))

    # Statutes are evergreen — even a 1860 Act is fully authoritative
    # unless superseded (which is handled by version control, not freshness)
    return 0.95
```

---

## 7.I — Knowledge Quality Monitor

> The knowledge base must not silently degrade. Stage 7 includes a quality monitoring service
> that alerts when sources go stale, connector errors accumulate, or embedding quality drops.

### 7.I.1 Quality Checks

New module: `backend/app/knowledge/quality_monitor.py`

```python
class KnowledgeQualityMonitor:
    """
    Runs daily. Checks:

    1. Staleness check: any source not synced in > STALE_THRESHOLD_HOURS hours?
       Flag and log a WARNING. If > 2x STALE_THRESHOLD_HOURS, flag as ERROR.

    2. Error rate check: any connector with error_count > ERROR_COUNT_THRESHOLD?
       Disable the connector and alert.

    3. Embedding coverage: what percentage of chunks have embeddings?
       If < 95%, trigger a re-embedding job for pending_embed chunks.

    4. Duplicate rate check: if > 5% of recent ingestion attempts are duplicates,
       log INFO (normal for incremental syncs after no changes).

    5. Corpus size trend: total chunk count per source_type over time.
       Sudden drops (> 20% in one sync) flag a potential connector issue.
    """
    async def run(self) -> QualityReport: ...
```

### 7.I.2 Quality Monitor API

```
GET /admin/knowledge/quality    -> latest quality report
GET /admin/knowledge/stats      -> corpus statistics (total docs, chunks, by source_type)
```

---

## 7.J — Environment Variables (Stage 7 Additions)

```ini
# 7.A Connectors
INDIA_CODE_BASE_URL=https://www.indiacode.nic.in
INDIA_CODE_API_KEY=
INDIAN_KANOON_API_KEY=
MCP_RSS_FEEDS=https://pib.gov.in/rss/rss.aspx,https://www.barandbench.com/feed
CONNECTOR_ENCRYPTION_KEY=           # AES-256 key for credential encryption

# 7.B Ingestion Pipeline
MAX_DOCUMENT_SIZE_CHARS=500000
CHUNK_MIN_CHARS=100
EMBED_BATCH_SIZE=32

# 7.D Sync Service
SYNC_INDIA_CODE_SCHEDULE=0 2 * * 0
SYNC_GAZETTE_SCHEDULE=0 */6 * * *
SYNC_SC_JUDGMENTS_SCHEDULE=0 8 * * *
SYNC_RSS_SCHEDULE=*/30 * * * *
SYNC_INITIAL_DELAY_MINUTES=5

# 7.G Trust
TRUST_SCORE_TIER1=1.0
TRUST_SCORE_TIER2=0.80
TRUST_SCORE_TIER3=0.65

# 7.I Quality Monitor
STALE_THRESHOLD_HOURS=48
ERROR_COUNT_THRESHOLD=10
QUALITY_MONITOR_SCHEDULE=0 6 * * *  # daily at 6am
```

---

## 7.K — New Files Summary

| File | Purpose |
|------|---------|
| `backend/app/knowledge/connectors/base.py` | `BaseConnector`, `RawDocument` |
| `backend/app/knowledge/connectors/india_code.py` | India Code connector |
| `backend/app/knowledge/connectors/gazette.py` | Gazette connector |
| `backend/app/knowledge/connectors/sc_judgment.py` | SC Judgment connector |
| `backend/app/knowledge/connectors/indian_kanoon.py` | Indian Kanoon API connector |
| `backend/app/knowledge/connectors/rss.py` | Generic RSS connector |
| `backend/app/knowledge/connectors/user_upload.py` | User upload connector (refactor from upload.py) |
| `backend/app/knowledge/connectors/registry.py` | Connector registry |
| `backend/app/knowledge/ingestion_pipeline.py` | 10-stage ingestion pipeline |
| `backend/app/knowledge/chunkers/legal_chunker.py` | Section-boundary statute chunker |
| `backend/app/knowledge/chunkers/paragraph_chunker.py` | Paragraph-boundary chunker |
| `backend/app/knowledge/chunkers/sliding_window_chunker.py` | Sliding window chunker |
| `backend/app/knowledge/change_detector.py` | Document diff computation |
| `backend/app/knowledge/sync_service.py` | Scheduled sync service |
| `backend/app/knowledge/quality_monitor.py` | Knowledge quality checks |
| `backend/app/routes/knowledge.py` | Knowledge store admin API |
| `alembic/versions/XXXX_knowledge_store.py` | DB migration for knowledge tables |
| `alembic/versions/XXXX_connector_configs.py` | DB migration for connector config table |

---

## 7.L — Modified Files Summary

| File | What changes |
|------|-------------|
| `backend/app/routes/upload.py` | Refactor to call `UserUploadConnector` → `IngestionPipeline` instead of inline ingestion logic. Preserves all API contracts. |
| `backend/app/routes/admin.py` | Add connector admin routes, sync admin routes, knowledge quality routes. |
| `backend/app/main.py` | Start sync service scheduler at lifespan startup. Start quality monitor scheduler. |
| `backend/app/config.py` | Add all env vars from 7.J. |

---

## 7.M — Testing Plan

| Test file | What is tested |
|-----------|---------------|
| `tests/test_connectors.py` | Each connector: authenticate (mocked), fetch returns RawDocument list |
| `tests/test_ingestion_pipeline.py` | Each pipeline stage independently. Full pipeline with mock connector. |
| `tests/test_legal_chunker.py` | Section boundary detection. Single-section fallback. |
| `tests/test_deduplication.py` | Exact duplicate skipped. Content-changed = new version created. |
| `tests/test_version_control.py` | Old version marked is_current=False on update. Rollback logic. |
| `tests/test_sync_service.py` | Since-based incremental fetch. Cache invalidation triggered. |
| `tests/test_change_detector.py` | No change = changed=False. Section added = correct report. |
| `tests/test_trust_scores.py` | Correct tier assignment per source_type. |
| `tests/test_freshness_score.py` | Gazette decays faster than statutes. |
| `tests/test_quality_monitor.py` | Staleness detection. Embedding coverage check. |
| `tests/test_knowledge_api.py` | CRUD on knowledge documents via admin API. Rollback. |

### Manual Verification Before Sign-Off

1. Run a full sync for India Code. Confirm document count increases in `GET /knowledge/stats`.
2. Modify one Act's text in the test fixture. Re-run sync. Confirm a new version is created
   and the old version's chunks have `is_active=FALSE`.
3. Query the chat endpoint with a question about that Act. Confirm the answer reflects the
   updated text (retrieved from the new version).
4. Upload a user PDF. Confirm it appears in `GET /me/documents`. Query the chat about content
   in that PDF. Confirm it is retrieved as a Tier-2 source.
5. Delete the uploaded document via `DELETE /me/documents/{id}`. Confirm it no longer appears
   in retrieval results.
6. Trigger an RSS sync. Confirm news chunks appear with trust_score=0.65 in the citation panel.
7. Run `GET /admin/knowledge/quality`. Confirm embedding coverage is > 95%.

---

## 7.N — Execution Order Within Stage 7

```
7.B  Ingestion Pipeline (all 10 stages)
 ↓
7.C  Knowledge Store tables (Alembic migration)
 ↓
7.A  Connector: UserUploadConnector (refactor upload.py to use pipeline)
 ↓
7.A  Connector: IndiaCodeConnector + full ingestion test
 ↓
7.A  Connector: GazetteConnector
 ↓
7.A  Connector: SCJudgmentConnector
 ↓
7.A  Connector: GenericRSSConnector
 ↓
7.A  Connector: IndianKanoonConnector (if API key available)
 ↓
7.D  Sync Service (scheduler + incremental sync)
 ↓
7.D  Change Detection + Version Control
 ↓
7.F  Connector Config table + admin API
 ↓
7.G  Trust tier assignment validation
 ↓
7.H  Freshness scoring integration
 ↓
7.E  User Knowledge API (document list, matter documents)
 ↓
7.I  Quality Monitor
 ↓
Full test suite (7.M) — sign off only when all pass
```

---

## 7.O — Hard Constraints

1. **No connector writes directly to the vector database.** Every document must pass
   through all 10 stages of the ingestion pipeline. No exceptions.
2. **No knowledge in the model.** This constraint is stated in Stage 5 and repeated here.
   Stage 7 is the correct place to update knowledge. The model is never involved.
3. **Version history is never deleted.** Documents can be soft-deleted (is_active=FALSE).
   Version rows are never hard-deleted. The audit trail is permanent.
4. **User documents are workspace-scoped.** A chunk with `workspace_id` set is never returned
   to a different user's session. Stage 1's ownership model extends to the knowledge store.
5. **Sync failures are non-fatal.** A connector failure logs an error and skips that source.
   The application continues serving queries from the existing knowledge base. No user impact.
6. **Re-embedding is incremental.** Only changed chunks are re-embedded. The entire corpus
   is never re-embedded unless explicitly triggered by an admin.
