import json
import asyncio
import logging
from typing import AsyncIterator, Dict, Any, Optional

logger = logging.getLogger(__name__)


def format_sse_event(data: Dict[str, Any], event_type: Optional[str] = None) -> str:
    """Formats a dictionary into Server-Sent Events (SSE) standard protocol."""
    event_str = f"event: {event_type}\n" if event_type else ""
    payload = json.dumps(data, ensure_ascii=False)
    return f"{event_str}data: {payload}\n\n"


async def stream_token_generator(
    token_stream: AsyncIterator[str],
    session_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> AsyncIterator[str]:
    """
    Asynchronously yields SSE events for tokens while monitoring for cancellation/exceptions.
    Guarantees clean release of resources on client disconnection.
    """
    full_text = []
    
    # Initial start event
    start_payload = {"session_id": session_id, "status": "generating"}
    if metadata:
        start_payload.update(metadata)
    yield format_sse_event(start_payload, event_type="start")

    try:
        async for token in token_stream:
            full_text.append(token)
            yield format_sse_event({"token": token, "done": False}, event_type="token")
            # Yield control to event loop to allow cancellation checks
            await asyncio.sleep(0.001)

        # Completion event
        yield format_sse_event({
            "session_id": session_id,
            "done": True,
            "total_chars": sum(len(t) for t in full_text)
        }, event_type="done")

    except asyncio.CancelledError:
        logger.info(f"Stream cancelled by client for session={session_id}")
        yield format_sse_event({"session_id": session_id, "status": "cancelled"}, event_type="cancelled")
        raise
    except Exception as exc:
        logger.error(f"Stream error for session={session_id}: {exc}")
        yield format_sse_event({"session_id": session_id, "error": str(exc)}, event_type="error")
