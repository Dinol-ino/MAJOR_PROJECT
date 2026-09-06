import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.observability.metrics import metrics_collector, RequestMetric


class TestDiagnosticsEndpoints(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_get_diagnostics_overview(self):
        res = self.client.get("/diagnostics")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("system_resources", data)
        self.assertIn("network_isolation", data)
        self.assertIn("runtime_status", data)
        self.assertIn("circuit_breakers", data)
        self.assertIn("metrics_summary", data)

    def test_get_diagnostics_metrics_summary(self):
        res = self.client.get("/diagnostics/metrics/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_requests", data)
        self.assertIn("p50_total_ms", data)
        self.assertIn("avg_ttft_ms", data)

    def test_get_diagnostics_trace(self):
        req_id = "req_diag_test_99"
        metric = RequestMetric(
            request_id=req_id,
            total_duration_ms=45.0,
            endpoint="/chat"
        )
        metrics_collector.record_request_metric(metric)

        res = self.client.get(f"/diagnostics/trace/{req_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["request_id"], req_id)
        self.assertEqual(data["total_duration_ms"], 45.0)

    def test_get_diagnostics_trace_404_for_unknown_id(self):
        res = self.client.get("/diagnostics/trace/req_nonexistent_xyz")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
