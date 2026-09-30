"""Measure the local (no-LLM) pipeline on THIS machine. Uses temporary stores; touches no user data.

    python scripts/measure_performance.py

Reports statute indexing time, retrieval latency (p50/p95) and vault PDF ingestion time.
Model generation latency needs Ollama and is measured separately.
"""
import json, os, statistics, sys, tempfile, time

tmp = tempfile.mkdtemp(prefix="dfrag_perf_")
for k, v in {"DATABASE_URL": "", "SQLITE_DB_PATH": f"{tmp}/db.sqlite", "CHROMA_PERSIST_DIR": f"{tmp}/chroma",
             "BM25_INDEX_DIR": f"{tmp}/bm25", "VAULT_FILES_DIR": f"{tmp}/vf", "PROVISIONING_DB_PATH": f"{tmp}/p.db",
             "OLLAMA_URL": "http://127.0.0.1:9", "NETWORK_MODE": "OFFLINE", "HF_HUB_OFFLINE": "1",
             "JWT_SECRET_KEY": "perf-only-key-0123456789abcdefghijklmnopqrstuv"}.items():
    os.environ[k] = v
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import asyncio  # noqa: E402
from app.db.engine import init_db_schema  # noqa: E402
asyncio.run(init_db_schema())
from app.ingestion.statutory_corpus import index_statutory_corpus  # noqa: E402
from app.retrieval.tier1_law import Tier1LawRetrieval  # noqa: E402
from app.config import settings  # noqa: E402


def pct(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(len(xs) * p))]


t = time.perf_counter(); stats = index_statutory_corpus(); index_s = time.perf_counter() - t
t1 = Tier1LawRetrieval(persist_dir=settings.CHROMA_PERSIST_DIR)
queries = ["punishment for cheating", "Section 138 of the Negotiable Instruments Act", "Section 302 IPC",
           "dishonour of cheque notice period", "anticipatory bail", "data fiduciary obligations",
           "director liability for fraud", "arbitration agreement validity", "electronic signature validity",
           "consideration in a contract"]
t1.query(queries[0], top_k=5)  # warm
from app.cache import l2_retrieval_cache  # noqa: E402
lat, warm = [], []
for _ in range(5):
    for q in queries:
        l2_retrieval_cache.clear()  # cold: measure retrieval itself, not the cache
        t = time.perf_counter(); t1.query(q, top_k=5); lat.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter(); t1.query(q, top_k=5); warm.append((time.perf_counter() - t) * 1000)

import fitz  # noqa: E402
d = fitz.open()
for i in range(60):
    p = d.new_page()
    p.insert_text((72, 100), f"Clause {i}. The parties agree that obligation number {i} shall be performed in Mangaluru. " * 3)
pdf = d.tobytes()
from app.services.document_store import document_store  # noqa: E402
from app.services.ingest import ingest_service  # noqa: E402
from app.db.engine import get_sync_session  # noqa: E402
from app.db.models import DocumentMemory, ProjectVault  # noqa: E402
with get_sync_session() as s:
    s.add(ProjectVault(id="v_perf", user_id="u", vault_name="perf")); s.commit()
    spath = document_store.save("v_perf", "d_perf", pdf)
    s.add(DocumentMemory(doc_id="d_perf", project_vault_id="v_perf", filename="perf.pdf", storage_path=spath, ingest_status="pending", ingest_progress=0)); s.commit()
t = time.perf_counter(); ingest_service.ingest_document(doc_id="d_perf", vault_id="v_perf", filename="perf.pdf"); ingest_s = time.perf_counter() - t
vl = []
for _ in range(20):
    t = time.perf_counter(); ingest_service.query_vault("v_perf", "where is obligation 7 performed", top_k=5); vl.append((time.perf_counter() - t) * 1000)

print(json.dumps({"acts": stats["acts_indexed"], "sections": stats["sections_indexed"], "statute_index_seconds": round(index_s, 2),
    "statute_query_ms_cold": {"p50": round(statistics.median(lat), 1), "p95": round(pct(lat, .95), 1), "n": len(lat)},
    "statute_query_ms_cached": {"p50": round(statistics.median(warm), 2), "p95": round(pct(warm, .95), 2)},
    "pdf_60_pages_ingest_seconds": round(ingest_s, 2),
    "vault_query_ms": {"p50": round(statistics.median(vl), 1), "p95": round(pct(vl, .95), 1)},
    "dense_search": bool(stats.get("dense_indexed"))}, indent=2))
