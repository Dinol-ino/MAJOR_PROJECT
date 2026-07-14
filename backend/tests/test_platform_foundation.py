import unittest

from app.platform import models  # noqa: F401
from app.config import settings
from app.platform.database import Base
from app.platform.redis_store import SessionMemoryStore


class FakeRedis:
    def __init__(self):
        self.data = {}

    def set(self, key, value, ex=None):
        self.data[key] = value

    def get(self, key):
        return self.data.get(key)

    def delete(self, key):
        self.data.pop(key, None)


class TestPlatformFoundation(unittest.TestCase):
    def test_database_url_is_available(self):
        self.assertTrue(settings.database_url.startswith("postgresql+psycopg://"))

    def test_expected_relational_tables_exist(self):
        expected = {
            "documents",
            "document_versions",
            "uploads",
            "chunks",
            "chunk_embeddings",
            "sessions",
            "model_catalog",
            "retrieval_events",
            "audit_events",
        }
        self.assertTrue(expected.issubset(Base.metadata.tables.keys()))

    def test_stage1_embedding_manifest_has_no_vector_column(self):
        columns = Base.metadata.tables["chunk_embeddings"].columns.keys()
        self.assertNotIn("embedding", columns)
        self.assertIn("storage_status", columns)
        self.assertIn("embedding_ref", columns)

    def test_session_memory_store_roundtrip(self):
        store = SessionMemoryStore(redis_client=FakeRedis(), ttl_seconds=30)
        payload = {"messages": ["hello"], "sources": ["chunk-1"]}

        store.put_context("ABC123", payload)
        self.assertEqual(store.get_context("ABC123"), payload)

        store.clear_context("ABC123")
        self.assertIsNone(store.get_context("ABC123"))


if __name__ == "__main__":
    unittest.main()
