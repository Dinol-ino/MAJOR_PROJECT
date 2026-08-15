# Prerequisites — Before Running Any Stage

Split into three categories: **installable** (agent/script can do this), **credentials/accounts** (you do this once, manually, outside the agent), and **human decisions** (no tool substitutes for this — must be resolved before the relevant stage starts, not during).

Do this pass before pointing antigravity at Stage 1. Several stage files assume these already exist.

---

## A. Core runtime (needed before Stage 1)

| Tool | Purpose | Install |
|---|---|---|
| Python 3.11+ | Backend | python.org or system package manager |
| Node.js 20+ | Frontend build (React/Tauri) | nodejs.org |
| Redis | Short-term session memory (already in your stack) | `apt install redis` / `brew install redis` / Docker |
| PostgreSQL 15+ | Durable memory + corpus provenance | postgresql.org or Docker |
| **pgvector extension** | Vector storage inside Postgres | `CREATE EXTENSION vector;` after install — not automatic, must be enabled per-database |
| Git | Version control | — |

Manual step: after installing Postgres, you must run `CREATE EXTENSION vector;` yourself on the target database — this is not something a Python script does implicitly, it needs the extension binary present at the OS level (`postgresql-<version>-pgvector` package on Linux, or bundled if using a pgvector-ready Docker image like `pgvector/pgvector`).

---

## B. Stage 1 — Security & Validation

| Tool | Purpose | Notes |
|---|---|---|
| `guardrails-ai` (pip) | Output validation framework | `pip install guardrails-ai` |
| `spacy` (pip) + a model | Entity/token overlap scoring | `pip install spacy` then `python -m spacy download en_core_web_sm` (or `en_core_web_trf` for better accuracy, larger download ~400MB) |
| `presidio-analyzer` + `presidio-anonymizer` (pip) | PII scanning on ingest | Microsoft Presidio — also needs a spaCy model as a backend (same one as above works) |
| `transformers` + `torch` (pip) | Run injection classifier models | CPU-only torch build is fine for 86M–200M classifier models — don't pull the CUDA build unless you have a GPU you intend to use |
| Injection classifier model weights | Layer 1/1.5 gate | **Manual/credentialed step** — see section D below, Meta's Prompt Guard is gated |
| Rate limiting library | e.g. `slowapi` (FastAPI) or equivalent for your framework | `pip install slowapi` — uses Redis as backend, which you already have |
| PDF sanitization library | `pikepdf` or `PyMuPDF` (`pip install pymupdf`) | Pick one; PyMuPDF also gives you page-level extraction needed later for citation `page` field |

**Human decision (blocking Stage 1 exit criteria item 9):** decide and document which Guardrails validators are approved for use — confirm each one is local-only before enabling. This is a review task, not an install.

---

## C. Stage 2 — Retrieval & Corpus

| Tool | Purpose | Notes |
|---|---|---|
| InLegalBERT weights | Embedding model | Downloads automatically via `transformers`/`sentence-transformers` on first use from `law-ai/InLegalBERT` on Hugging Face — no gating, no login required, but it's a first-run download (~450MB), do it once ahead of time so Stage 2 doesn't stall mid-ingestion |
| `rank_bm25` (pip) | Sparse retrieval | `pip install rank_bm25` — lightweight, no external service needed |
| `playwright` (pip) + browser binaries | JS-rendered site scraping | `pip install playwright` then **`playwright install chromium`** — this is a separate ~300MB browser binary download, not covered by pip install alone |
| `httpx` or `requests` (pip) | Direct HTTP fetch for non-JS sources | Prefer this over Playwright wherever a site doesn't need JS rendering — faster, lighter, less to maintain |

**Human decision (blocking Stage 2 Part B, item B1):** confirm and document which sources are cleared for bulk scraping. Concretely:
- Check India Code's (indiacode.nic.in) current terms/robots.txt before automated bulk fetch.
- If using any High Court site, check that specific court's terms individually — no blanket assumption.
- Do not point the Stage 2 ingestion pipeline at IndianKanoon for bulk scraping without someone confirming current terms allow it.

This is not something to defer to "check it while coding" — resolve it first, since the ingestion pipeline's source list depends on the answer.

---

## D. Credentials / accounts needed

| Account | Why | Notes |
|---|---|---|
| **Hugging Face account + access token** | Some model weights are gated | Meta's **Prompt Guard 86M** requires accepting Meta's license on the model page before download works — log in to huggingface.co, visit the model page, accept terms, then generate a token (`HF_TOKEN` env var) for `transformers` to authenticate. If you'd rather avoid gating entirely, use **ProtectAI's DeBERTa-v3-v2 prompt injection model** instead — ungated, works without a token. |
| **Ollama** | Local model serving (all generation) | Not a pip package — separate installer from ollama.com for your OS. After install, `ollama pull llama3.2:3b` for the Tier 0 floor model before Stage 4 testing. |
| **Google account (for Colab)** | Stage 5 fine-tuning | Free tier works for LoRA on a 7B model with quantization; no separate signup needed beyond a Google account, but confirm Colab GPU availability isn't rate-limited on the free tier if you're on it — paid Colab Pro removes that friction if it becomes a blocker. |
| **Rust toolchain (`rustup`) + Tauri CLI** | Stage 6 desktop packaging | `rustup` from rust-lang.org, then `cargo install tauri-cli` — required regardless of your primary language being Python, since Tauri's shell is Rust. Also needs platform-specific webview dependencies (WebView2 runtime on Windows — usually preinstalled on Win10/11; `webkit2gtk` on Linux via package manager). |
| **Docker + Docker Compose** | Stage 6 server path | docker.com — install once, no account required for local use. |

---

## E. Stage 5 — Fine-tuning specific

| Tool | Purpose | Notes |
|---|---|---|
| `peft`, `bitsandbytes`, `accelerate` (pip, inside Colab) | LoRA/QLoRA training | Installed inside the Colab notebook itself, not on your local machine — no local GPU needed per your existing plan |
| Base model access on Hugging Face | Fine-tuning target (Mistral-7B or SaulLM-7B) | SaulLM-7B (`Equall/Saul-7B-Instruct-v1` or similar naming — verify exact repo ID on HF at the time) is ungated as of general availability; Mistral-7B-Instruct is also ungated. Confirm the exact model card doesn't require a separate license click-through before scripting the Colab pull. |

---

## F. Eval harness (07)

| Tool | Purpose | Notes |
|---|---|---|
| `ragas` (pip) | Faithfulness/precision/recall scoring | `pip install ragas` |
| `datasets` (pip) | RAGAS dependency for handling eval sets | Usually pulled in automatically by `ragas`, listed here in case it isn't |

**Human task, not a tool:** the curated legal-accuracy test set (question/ground-truth-citation pairs) has to be written by someone with legal domain familiarity. No package installs this — flag it as a standing task with an owner before Stage 2's retrieval work is considered "evaluated" rather than just "implemented."

---

## G. Order of operations for this checklist

1. Install core runtime (A) + enable pgvector extension manually.
2. Install Stage 1 packages, resolve the HF gating decision (D) for the injection classifier, download the spaCy model.
3. Install Stage 2 packages, run `playwright install chromium` once, pre-download InLegalBERT weights.
4. Install Ollama, pull the Tier 0 model.
5. Resolve the source-clearance decision (C) — do this before writing any ingestion code, not after.
6. Defer Rust/Tauri and Docker installs until you're actually approaching Stage 6 — no need to front-load them.
7. Set up the Colab notebook environment only when Stage 5 starts, per its own deferred-until-stable rule.

Everything in this file should be resolved (or explicitly deferred per the ordering above) before telling antigravity to begin executing `01_STAGE1_SECURITY_AND_VALIDATION.md`.
