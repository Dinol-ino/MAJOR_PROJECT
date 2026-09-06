import unittest
import time
from app.observability.metrics import metrics_collector, RequestMetric, StageMetric


class TestMetricsCollector(unittest.TestCase):

    def test_record_and_get_trace(self):
        req_id = f"req_test_{int(time.time() * 1000)}"
        metric = RequestMetric(
            request_id=req_id,
            session_id="sess_test_1",
            endpoint="/chat",
            total_duration_ms=85.2,
            api_overhead_ms=2.1,
            time_to_first_token_ms=25.0,
            generation_time_ms=50.0,
            retrieval_latency_ms=8.1,
            input_tokens=120,
            output_tokens=80,
            model_tier="TIER_0_CPU_FLOOR",
            stages=[
                StageMetric(stage_name="RETRIEVE", duration_ms=8.1),
                StageMetric(stage_name="SYNTHESIS", duration_ms=50.0)
            ]
        )

        metrics_collector.record_request_metric(metric)

        trace = metrics_collector.get_trace(req_id)
        self.assertIsNotNone(trace)
        self.assertEqual(trace["request_id"], req_id)
        self.assertEqual(trace["total_duration_ms"], 85.2)
        self.assertEqual(len(trace.get("stages", [])), 2)

    def test_get_summary_aggregates(self):
        # Record multiple metrics
        for i in range(5):
            m = RequestMetric(
                request_id=f"req_agg_{i}_{int(time.time() * 1000)}",
                total_duration_ms=10.0 * (i + 1),
                time_to_first_token_ms=5.0 * (i + 1),
                retrieval_latency_ms=3.0,
                cache_hits={"L1": 1, "L2": 0, "L3": 0},
                cache_misses={"L1": 0, "L2": 1, "L3": 0}
            )
            metrics_collector.record_request_metric(m)

        summary = metrics_collector.get_summary()
        self.assertGreaterEqual(summary["total_requests"], 5)
        self.assertGreater(summary["p50_total_ms"], 0.0)
        self.assertGreater(summary["avg_retrieval_ms"], 0.0)
        self.assertGreater(summary["cache_hit_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
