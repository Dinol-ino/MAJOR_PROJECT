import unittest
import uuid
from app.memory import (
    conversation_memory,
    semantic_memory,
    document_memory,
    policies,
)


class TestMemoryIsolation(unittest.TestCase):

    def setUp(self):
        self.user_a = f"lawyer_a_{uuid.uuid4().hex[:6]}"
        self.user_b = f"lawyer_b_{uuid.uuid4().hex[:6]}"

    def test_l2_conversation_isolation(self):
        conv_id = f"conv_priv_{uuid.uuid4().hex[:6]}"
        # User A creates a conversation and adds messages
        conversation_memory.get_or_create_conversation(conv_id, user_id=self.user_a, title="User A Confidential")
        conversation_memory.add_message(
            conversation_id=conv_id,
            role="user",
            content="Confidential client NDA details.",
            user_id=self.user_a
        )

        # User A can read messages
        msgs_a = conversation_memory.get_messages(conv_id, user_id=self.user_a)
        self.assertEqual(len(msgs_a), 1)

        # User B is blocked from reading User A's conversation
        with self.assertRaises(PermissionError):
            conversation_memory.get_messages(conv_id, user_id=self.user_b)

        # User B is blocked from deleting User A's conversation
        with self.assertRaises(PermissionError):
            conversation_memory.delete_conversation(conv_id, user_id=self.user_b)

    def test_l3_semantic_memory_isolation(self):
        # User A saves a preference
        entry_a = semantic_memory.propose_and_save(
            user_id=self.user_a,
            category="preference",
            key="drafting_style",
            value="Concise statutory citations",
            consent_given=True
        )

        # User B saves a different preference
        entry_b = semantic_memory.propose_and_save(
            user_id=self.user_b,
            category="preference",
            key="drafting_style",
            value="Detailed explanatory notes",
            consent_given=True
        )

        # User A sees only their own memory
        mems_a = semantic_memory.get_user_memories(self.user_a)
        self.assertEqual(len(mems_a), 1)
        self.assertEqual(mems_a[0]["value"], "Concise statutory citations")

        # User B sees only their own memory
        mems_b = semantic_memory.get_user_memories(self.user_b)
        self.assertEqual(len(mems_b), 1)
        self.assertEqual(mems_b[0]["value"], "Detailed explanatory notes")

        # User B cannot delete User A's memory
        with self.assertRaises(PermissionError):
            semantic_memory.delete_memory(entry_a["id"], user_id=self.user_b)

    def test_l4_document_session_isolation(self):
        sess_a = f"sess_a_{uuid.uuid4().hex[:6]}"
        sess_b = f"sess_b_{uuid.uuid4().hex[:6]}"

        document_memory.record_document(
            doc_id=f"doc_a_{uuid.uuid4().hex[:4]}",
            session_id=sess_a,
            filename="user_a_merger_agreement.pdf"
        )
        document_memory.record_document(
            doc_id=f"doc_b_{uuid.uuid4().hex[:4]}",
            session_id=sess_b,
            filename="user_b_arbitration_notice.pdf"
        )

        docs_a = document_memory.get_session_documents(sess_a)
        self.assertEqual(len(docs_a), 1)
        self.assertEqual(docs_a[0]["filename"], "user_a_merger_agreement.pdf")

        docs_b = document_memory.get_session_documents(sess_b)
        self.assertEqual(len(docs_b), 1)
        self.assertEqual(docs_b[0]["filename"], "user_b_arbitration_notice.pdf")


if __name__ == "__main__":
    unittest.main()
