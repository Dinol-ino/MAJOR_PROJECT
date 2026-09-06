import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.observability.correlation import (
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
    correlation_context,
    CorrelationMiddleware,
)


class TestCorrelationTracking(unittest.TestCase):

    def test_generate_and_set_correlation_id(self):
        cid = generate_correlation_id()
        self.assertTrue(cid.startswith("req_"))
        set_correlation_id(cid)
        self.assertEqual(get_correlation_id(), cid)

    def test_correlation_context_scoping(self):
        with correlation_context("req_custom_123") as cid:
            self.assertEqual(cid, "req_custom_123")
            self.assertEqual(get_correlation_id(), "req_custom_123")

    def test_middleware_attaches_and_returns_header(self):
        app = FastAPI()
        app.add_middleware(CorrelationMiddleware)

        @app.get("/ping")
        def ping():
            return {"correlation_id": get_correlation_id()}

        client = TestClient(app)

        # 1. Custom incoming header
        res1 = client.get("/ping", headers={"X-Correlation-ID": "req_incoming_999"})
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.headers.get("X-Correlation-ID"), "req_incoming_999")
        self.assertEqual(res1.json().get("correlation_id"), "req_incoming_999")

        # 2. Generated header
        res2 = client.get("/ping")
        self.assertEqual(res2.status_code, 200)
        generated_cid = res2.headers.get("X-Correlation-ID")
        self.assertIsNotNone(generated_cid)
        self.assertTrue(generated_cid.startswith("req_"))


if __name__ == "__main__":
    unittest.main()
