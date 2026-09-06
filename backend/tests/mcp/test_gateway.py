import unittest
from app.mcp.gateway import mcp_gateway, MCPResponse
from app.db.engine import get_sync_session
from app.db.models import MCPToolCall


class TestMCPGateway(unittest.TestCase):

    def test_execute_local_statute_search(self):
        resp: MCPResponse = mcp_gateway.execute_tool(
            tool_name="local_statute_search",
            arguments={"query": "punishment for murder", "top_k": 2},
            session_id="test_mcp_session",
            network_mode="OFFLINE"
        )
        self.assertTrue(resp.success)
        self.assertEqual(resp.category, "LOCAL_RETRIEVAL")
        self.assertIsNotNone(resp.data)
        self.assertTrue(resp.is_sanitized)

    def test_execute_provision_lookup(self):
        resp: MCPResponse = mcp_gateway.execute_tool(
            tool_name="local_provision_lookup",
            arguments={"act": "Indian Penal Code", "section": "Section 302"},
            session_id="test_mcp_session",
            network_mode="OFFLINE"
        )
        self.assertTrue(resp.success)
        self.assertEqual(resp.category, "LOCAL_RETRIEVAL")
        self.assertIn("found", resp.data)

    def test_blocked_policy_tool_execution(self):
        resp: MCPResponse = mcp_gateway.execute_tool(
            tool_name="live_statute_checker",
            arguments={"act_name": "Information Technology Act"},
            session_id="test_mcp_session",
            network_mode="OFFLINE"
        )
        self.assertFalse(resp.success)
        self.assertEqual(resp.category, "CURRENT_LAW")
        self.assertIn("requires ONLINE mode", resp.error)

    def test_tool_call_persisted_in_db(self):
        resp: MCPResponse = mcp_gateway.execute_tool(
            tool_name="local_provision_lookup",
            arguments={"act": "Indian Penal Code", "section": "Section 420"},
            session_id="test_db_persist_session",
            network_mode="OFFLINE"
        )
        self.assertTrue(resp.success)

        with get_sync_session() as session:
            record = session.query(MCPToolCall).filter(
                MCPToolCall.session_id == "test_db_persist_session",
                MCPToolCall.tool_name == "local_provision_lookup"
            ).order_by(MCPToolCall.id.desc()).first()
            self.assertIsNotNone(record)
            self.assertEqual(record.category, "LOCAL_RETRIEVAL")
            self.assertEqual(record.is_allowed, 1)


if __name__ == "__main__":
    unittest.main()
