"""
Hermetic test environment.

Runs before any test module imports the app, so every store points at a throwaway
directory and no test can touch a developer's real database, indexes or models,
or reach a real model runtime / the internet.
"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="dfrag_test_")
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

if os.environ.get("DFRAG_TEST_USE_ENV") != "1":
    os.environ["DATABASE_URL"] = ""
    os.environ["SQLITE_DB_PATH"] = os.path.join(_TMP, "dfrag_test.db")
    os.environ["CHROMA_PERSIST_DIR"] = os.path.join(_TMP, "chroma")
    os.environ["BM25_INDEX_DIR"] = os.path.join(_TMP, "bm25")
    os.environ["PROVISIONING_DB_PATH"] = os.path.join(_TMP, "provisioning.db")
    # Nothing listens on the discard port: runtime calls fail fast instead of hitting a real Ollama.
    os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"
    os.environ["OLLAMA_CONNECT_TIMEOUT_SECONDS"] = "0.5"
    os.environ["OLLAMA_PROBE_TIMEOUT_SECONDS"] = "0.5"
    os.environ["NETWORK_MODE"] = "OFFLINE"
    os.environ["AUTO_PULL_ON_STARTUP"] = "false"
    os.environ["MODEL_WARMUP_ON_STARTUP"] = "false"
    os.environ["CLOUD_FALLBACK_ENABLED"] = "false"
    os.environ["ACTS_RAW_DIR"] = os.path.join(_REPO_ROOT, "data", "acts_raw")
    os.environ.setdefault("JWT_SECRET_KEY", "test-only-signing-key-not-used-outside-pytest-0123456789")
    os.environ.setdefault("SECRET_KEY", "test-only-vault-key-not-used-outside-pytest-0123456789")
    os.environ["DFRAG_TEST_MODE"] = "1"

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _index_statutory_corpus():
    """Index the repository's real statutory corpus once (via the production pipeline)."""
    from app.ingestion.statutory_corpus import index_statutory_corpus
    stats = index_statutory_corpus()
    yield stats
