import os
import shutil
import tempfile
import unittest
from app.memory.durable_memory import DurableMemoryManager


class TestStage3Memory(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_transcript.db")
        self.memory = DurableMemoryManager(db_url_or_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_write_through_persistence_and_restart(self):
        # 1. Create session and log turns
        conv_id = "session_001"
        user_id = "user_alpha"

        self.memory.add_message(
            conversation_id=conv_id,
            role="user",
            content="What is Section 66 IT Act?",
            user_id=user_id
        )
        self.memory.add_message(
            conversation_id=conv_id,
            role="assistant",
            content="Section 66 specifies punishment for computer offences.",
            citations=[{"act": "IT Act", "section": "66"}],
            user_id=user_id
        )

        # 2. Verify conversation list
        convs = self.memory.get_user_conversations(user_id=user_id)
        self.assertEqual(len(convs), 1)
        self.assertEqual(convs[0]["conversation_id"], conv_id)

        # 3. Verify messages
        msgs = self.memory.get_conversation_messages(conv_id, user_id=user_id)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["role"], "assistant")
        self.assertEqual(msgs[1]["citations"][0]["act"], "IT Act")

        # 4. Simulate app restart with new manager instance reading existing DB file
        restarted_memory = DurableMemoryManager(db_url_or_path=self.db_path)
        restarted_convs = restarted_memory.get_user_conversations(user_id=user_id)
        self.assertEqual(len(restarted_convs), 1)

        restarted_msgs = restarted_memory.get_conversation_messages(conv_id, user_id=user_id)
        self.assertEqual(len(restarted_msgs), 2)

    def test_user_identity_isolation(self):
        conv_id1 = "session_user1"
        conv_id2 = "session_user2"
        user1 = "user_one"
        user2 = "user_two"

        self.memory.add_message(conv_id1, "user", "User 1 private question", user_id=user1)
        self.memory.add_message(conv_id2, "user", "User 2 private question", user_id=user2)

        # User 1 cannot see User 2's conversations or messages
        u1_convs = self.memory.get_user_conversations(user_id=user1)
        self.assertEqual(len(u1_convs), 1)
        self.assertEqual(u1_convs[0]["conversation_id"], conv_id1)

        u1_msgs_attempt_u2 = self.memory.get_conversation_messages(conv_id2, user_id=user1)
        self.assertEqual(len(u1_msgs_attempt_u2), 0)

    def test_semantic_memory_crud(self):
        self.memory.save_semantic_memory(
            user_id="lawyer_99",
            category="preference",
            key="preferred_language",
            value="Hindi/English mixed"
        )
        self.memory.save_semantic_memory(
            user_id="lawyer_99",
            category="fact",
            key="firm_name",
            value="Apex Legal Advocates"
        )

        all_mems = self.memory.get_semantic_memories(user_id="lawyer_99")
        self.assertEqual(len(all_mems), 2)

        pref_mems = self.memory.get_semantic_memories(user_id="lawyer_99", category="preference")
        self.assertEqual(len(pref_mems), 1)
        self.assertEqual(pref_mems[0]["value"], "Hindi/English mixed")

        # Update existing
        self.memory.save_semantic_memory(
            user_id="lawyer_99",
            category="preference",
            key="preferred_language",
            value="English"
        )
        updated_prefs = self.memory.get_semantic_memories(user_id="lawyer_99", category="preference")
        self.assertEqual(len(updated_prefs), 1)
        self.assertEqual(updated_prefs[0]["value"], "English")

    def test_document_memory_tracking(self):
        doc = self.memory.save_document_memory(
            doc_id="doc_test_101",
            session_id="session_doc_test",
            filename="case_brief.pdf",
            file_size_bytes=512000,
            page_count=5,
            chunk_count=10,
            metadata_json={"tag": "brief"}
        )
        self.assertEqual(doc["doc_id"], "doc_test_101")
        self.assertEqual(doc["filename"], "case_brief.pdf")

        docs = self.memory.get_session_documents("session_doc_test")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["page_count"], 5)


if __name__ == "__main__":
    unittest.main()
