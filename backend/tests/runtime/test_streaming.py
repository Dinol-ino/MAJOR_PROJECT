import unittest
import asyncio
from app.runtime.streaming import format_sse_event, stream_token_generator


class TestStreaming(unittest.TestCase):

    def test_format_sse_event(self):
        data = {"token": "Constitution", "done": False}
        formatted = format_sse_event(data, event_type="token")
        self.assertTrue(formatted.startswith("event: token\n"))
        self.assertIn('"token": "Constitution"', formatted)
        self.assertTrue(formatted.endswith("\n\n"))

    async def async_test_stream_token_generator(self):
        async def mock_token_stream():
            tokens = ["Article", " ", "21", " ", "guarantees", " ", "life."]
            for t in tokens:
                yield t

        events = []
        async for sse in stream_token_generator(mock_token_stream(), session_id="test_sess_123"):
            events.append(sse)

        # First event is start, last event is done
        self.assertTrue(events[0].startswith("event: start\n"))
        self.assertTrue(events[-1].startswith("event: done\n"))
        # Intermediate events contain tokens
        token_events = [e for e in events if "event: token\n" in e]
        self.assertEqual(len(token_events), 7)

    def test_stream_token_generator_wrapper(self):
        asyncio.run(self.async_test_stream_token_generator())


if __name__ == "__main__":
    unittest.main()
