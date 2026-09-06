import unittest
from app.research.pipeline import research_pipeline, ResearchPipelineResult
from app.research.provenance import validate_provenance_completeness
from app.network.mode_enforcer import mode_enforcer


class TestResearchPipeline(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        mode_enforcer.set_mode("OFFLINE", reason="Pipeline test setup")

    async def asyncTearDown(self):
        mode_enforcer.set_mode("OFFLINE", reason="Pipeline test teardown")

    async def test_pipeline_offline_mode_surfaces_freshness_notice(self):
        res: ResearchPipelineResult = await research_pipeline.execute_research(
            query="What is the latest 2024 amendment and status of Section 302 IPC?",
            session_id="test_pipe_offline_session",
            force_mode="OFFLINE"
        )
        self.assertEqual(res.network_mode_used, "OFFLINE")
        self.assertTrue(res.freshness_required)
        self.assertIsNotNone(res.offline_notice)
        self.assertIn("OFFLINE mode", res.offline_notice)

        # Confirm all local evidence items carry 100% complete provenance
        self.assertGreater(len(res.evidence_items), 0)
        for item in res.evidence_items:
            self.assertTrue(validate_provenance_completeness(item.provenance))
            self.assertEqual(item.provenance.trust_level, "LOCAL_VERIFIED_CORPUS")

    async def test_pipeline_online_mode_executes_with_provenance(self):
        mode_enforcer.set_mode("ONLINE", reason="Testing online pipeline")
        res: ResearchPipelineResult = await research_pipeline.execute_research(
            query="What is the current legal status of Indian Penal Code Section 420?",
            session_id="test_pipe_online_session",
            force_mode="ONLINE"
        )
        self.assertEqual(res.network_mode_used, "ONLINE")
        self.assertGreater(len(res.evidence_items), 0)

        # Confirm all evidence items have complete provenance
        for item in res.evidence_items:
            self.assertTrue(validate_provenance_completeness(item.provenance))
            self.assertIn(item.provenance.trust_level, ["LOCAL_VERIFIED_CORPUS", "OFFICIAL_GAZETTE", "AUTHORITATIVE_PORTAL"])


if __name__ == "__main__":
    unittest.main()
