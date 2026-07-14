# Stage 2: Ingestion and PageIndex

## Objective

Move from plain PDF text extraction and shallow chunk metadata to a structured ingestion pipeline that produces a durable legal document graph.

## Target state

- `PyMuPDF` is the primary parser when installed.
- `pdfplumber` remains a PDF fallback so local development is not blocked.
- `PaddleOCR` runs only when enabled and when page text extraction is poor.
- `PDF`, `DOCX`, and `TXT` are accepted inputs by the backend contract.
- Every ingested document produces a deterministic `PageIndex` with document, chapter, section, paragraph, and chunk trace metadata.

## Implementation completed

- Added typed ingestion contracts in `backend/app/ingestion/types.py`.
- Added `DocumentParser` in `backend/app/ingestion/document_parser.py`.
- Added durable ingestion persistence through `IngestionRepository` and `IngestionService`.
- Extended `PageIndexBuilder` with deterministic document, version, section-parent, and chunk IDs while preserving the old section extraction API.
- Updated `/upload` to accept `.pdf`, `.txt`, and `.docx`, persist raw files, store relational PageIndex chunks, and optionally keep the legacy Chroma write path during cutover.
- Kept uploaded document storage unbound from `session_id`; uploads are stored under the configured workspace scope.
- Added Stage 2 tests for parsing, unsupported type rejection, stable PageIndex metadata, cross-page section page-number preservation, live PostgreSQL persistence, and upload-route TXT ingestion.

## Required metadata on each chunk

Implemented through `PageIndexChunk` fields plus persisted `Chunk.metadata_json`:

- `document_id`
- `document_version`
- `page_number`
- `heading_path`
- `section_label`
- `chunk_id`
- `parent_id`
- `hash` / `content_hash`
- `corpus_type`
- `source_filename`
- `mime_type`

## Why this stage is before retrieval migration

The vector layer is only as good as the chunk structure it indexes. If chunk identity, page numbers, and headings are weak, later trust scoring and explainability will be weak too.

## Required installs

Declared in `backend/requirements.txt`:

- `PyMuPDF>=1.24,<2`
- `python-docx>=1.1,<2`

Already present fallback support:

- `pdfplumber==0.11.*`

Optional, not installed by default:

- `PaddleOCR`
- OCR runtime dependencies required by the chosen Windows/Docker runtime

## Required `.env` values

Documented in `.env.example` and wired into `docker-compose.yml`:

- `UPLOAD_ROOT`
- `DEFAULT_WORKSPACE_ID`
- `MAX_FILE_SIZE_MB`
- `MAX_FILE_PAGES`
- `OCR_ENABLED`
- `OCR_LANGUAGE`
- `OCR_MIN_TEXT_THRESHOLD`

Do not store Hugging Face tokens or OCR secrets in committed files. Use local `.env` only.

## In scope

- file type handling strategy
- parser fallback order
- page- and section-aware chunk identity
- chunk hashing
- persistent raw file strategy
- relational upload/chunk persistence

## Out of scope

- embeddings
- reranking
- generator swap
- Langfuse
- pgvector server extension or vector columns

## Important design rule

Do not bind user uploads to `session_id` at the storage level. Bind them to a durable owner scope such as `workspace_id` or `user_id`, then authorize session access separately.

## Verification

Run from `project/backend`:

```powershell
.\venv\Scripts\python.exe -m compileall app tests
.\venv\Scripts\python.exe -m pytest tests
```

Latest result on 2026-07-14:

- `compileall`: passed
- `pytest tests`: `22 passed, 2 warnings`

Warnings are Alembic deprecation warnings for `path_separator` configuration and are not Stage 2 functional failures.

## Exit criteria

- The ingestion contract can produce stable chunk identities. Done.
- Any chunk returned later can be traced back to file, page, and heading. Done.
- OCR is optional and conditional, not a mandatory cost on all uploads. Done.
