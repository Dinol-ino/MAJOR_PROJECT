import unittest
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    Base,
    Conversation,
    Message,
    SemanticMemory,
    DocumentMemory,
    ResearchSession,
    AuditEvent,
)
from app.db.engine import init_db_schema
from app.db.health import check_db_health


class TestDBPersistence(unittest.TestCase):
    def setUp(self):
        # Create an in-memory SQLite database for isolated test execution
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_models_instantiation_and_dict(self):
        conv = Conversation(
            conversation_id="conv_123",
            user_id="user_1",
            title="Legal Query on IT Act",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        d = conv.to_dict()
        self.assertEqual(d["conversation_id"], "conv_123")
        self.assertEqual(d["user_id"], "user_1")
        self.assertEqual(d["title"], "Legal Query on IT Act")

        msg = Message(
            message_id="msg_001",
            conversation_id="conv_123",
            role="user",
            content="What are the penalties under Section 66?",
            citations=[{"act": "IT Act", "section": "66"}],
            blocked_by=None,
            latency_ms=12.5,
            created_at=datetime.utcnow(),
        )
        msg_d = msg.to_dict()
        self.assertEqual(msg_d["message_id"], "msg_001")
        self.assertEqual(msg_d["citations"][0]["act"], "IT Act")

    def test_crud_and_cascade_delete(self):
        with self.Session() as session:
            conv = Conversation(
                conversation_id="conv_cascade_test",
                user_id="user_test",
                title="Test Cascade",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(conv)
            session.commit()

            msg1 = Message(
                message_id="msg_c1",
                conversation_id="conv_cascade_test",
                role="user",
                content="Hello",
                created_at=datetime.utcnow(),
            )
            msg2 = Message(
                message_id="msg_c2",
                conversation_id="conv_cascade_test",
                role="assistant",
                content="Hello, how can I help with Indian Law?",
                created_at=datetime.utcnow(),
            )
            session.add_all([msg1, msg2])
            session.commit()

            # Verify query
            fetched_conv = session.query(Conversation).filter_by(conversation_id="conv_cascade_test").first()
            self.assertIsNotNone(fetched_conv)
            self.assertEqual(len(fetched_conv.messages), 2)

            # Delete conversation should cascade delete messages
            session.delete(fetched_conv)
            session.commit()

            remaining_msgs = session.query(Message).filter_by(conversation_id="conv_cascade_test").all()
            self.assertEqual(len(remaining_msgs), 0)

    def test_transaction_rollback_on_error(self):
        with self.Session() as session:
            try:
                conv = Conversation(
                    conversation_id="conv_err_test",
                    user_id="user_err",
                    title="Will Rollback",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(conv)
                # Intentionally insert a conflicting primary key to provoke rollback
                conv_duplicate = Conversation(
                    conversation_id="conv_err_test",
                    user_id="user_err_2",
                    title="Duplicate PK",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(conv_duplicate)
                session.commit()
            except Exception:
                session.rollback()

            # Verify nothing was persisted
            persisted = session.query(Conversation).filter_by(conversation_id="conv_err_test").first()
            self.assertIsNone(persisted)

    def test_semantic_and_document_memory(self):
        with self.Session() as session:
            sem = SemanticMemory(
                id=str(uuid.uuid4()),
                user_id="lawyer_42",
                category="preference",
                key="jurisdiction",
                value="High Court of Delhi",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            doc = DocumentMemory(
                doc_id="doc_xyz",
                session_id="session_abc",
                filename="arbitration_agreement.pdf",
                file_size_bytes=1048576,
                page_count=12,
                chunk_count=24,
                metadata_json={"type": "commercial_contract"},
                created_at=datetime.utcnow(),
            )
            session.add_all([sem, doc])
            session.commit()

            fetched_sem = session.query(SemanticMemory).filter_by(user_id="lawyer_42").first()
            self.assertEqual(fetched_sem.value, "High Court of Delhi")

            fetched_doc = session.query(DocumentMemory).filter_by(session_id="session_abc").first()
            self.assertEqual(fetched_doc.filename, "arbitration_agreement.pdf")

    def test_audit_event_persistence(self):
        with self.Session() as session:
            event = AuditEvent(
                ts="2026-08-27T00:00:00Z",
                action="chat_inference",
                layer="runtime",
                injection_score=0.02,
                retrieval_hits=3,
                citations_used=1,
                validation_pass_fail="pass",
                model_tier_used="Tier 0 (Standard Floor)",
                latency_ms=154.2,
                hash="a"*64,
                prev_hash="0"*64,
            )
            session.add(event)
            session.commit()

            fetched_event = session.query(AuditEvent).filter_by(action="chat_inference").first()
            self.assertIsNotNone(fetched_event)
            self.assertEqual(fetched_event.latency_ms, 154.2)

    def test_db_health_check_structure(self):
        import asyncio
        health = asyncio.run(check_db_health())
        self.assertIn("status", health)
        self.assertIn("latency_ms", health)
        self.assertIn("pool", health)

    def test_sync_session_context_manager(self):
        from app.db.engine import get_sync_session
        # Ensure session context manager functions properly
        with get_sync_session() as session:
            self.assertIsNotNone(session)


if __name__ == "__main__":
    unittest.main()
