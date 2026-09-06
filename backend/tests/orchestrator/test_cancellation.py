import unittest
from app.orchestrator.cancellation import CancellationManager


class TestCancellationManager(unittest.TestCase):

    def setUp(self):
        self.mgr = CancellationManager()

    def test_register_and_cancel_lifecycle(self):
        req_id = "test_req_123"
        self.mgr.register(req_id)
        self.assertFalse(self.mgr.is_cancelled(req_id))

        self.mgr.cancel(req_id, reason="User interrupted research")
        self.assertTrue(self.mgr.is_cancelled(req_id))
        self.assertEqual(self.mgr.get_cancellation_reason(req_id), "User interrupted research")

        self.mgr.unregister(req_id)
        self.assertFalse(self.mgr.is_cancelled(req_id))


if __name__ == "__main__":
    unittest.main()
