import unittest
from unittest.mock import AsyncMock, patch
from app.runtime.manager import runtime_manager
from app.memory.audit_memory import audit_memory


class TestOOMFallback(unittest.TestCase):

    async def async_test_oom_recovery(self):
        prompt = "Analyze Indian Penal Code Section 420 in light of recent jurisprudence."

        # Simulate OOM failure on the primary model call, then success on fallback call
        mock_generate = AsyncMock()
        mock_generate.side_effect = [
            RuntimeError("CUDA out of memory: tried to allocate 2.00 GiB"),
            "Section 420 deals with cheating and dishonestly inducing delivery of property."
        ]

        with patch.object(runtime_manager._runtime, "generate", mock_generate):
            result = await runtime_manager.generate_with_oom_recovery(
                prompt=prompt,
                task_type="legal_reasoning",
                preferred_model="qwen2.5:14b"
            )

            self.assertEqual(result["status"], "degraded_success")
            self.assertTrue(result["fallback_occurred"])
            self.assertIn("Section 420", result["answer"])
            self.assertIn("fallback", result["notice"].lower())

            # Verify that fallback event was written to L6 Audit Memory
            recent_audits = audit_memory.get_recent_events(limit=5)
            fallback_events = [e for e in recent_audits if e.get("action") == "model_oom_fallback"]
            self.assertTrue(len(fallback_events) >= 1)

    def test_oom_recovery_wrapper(self):
        import asyncio
        asyncio.run(self.async_test_oom_recovery())


if __name__ == "__main__":
    unittest.main()
