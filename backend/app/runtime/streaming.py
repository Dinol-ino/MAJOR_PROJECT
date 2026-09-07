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
    Extracts <deep_thinking>...</deep_thinking> blocks and emits {type: "reasoning_delta"}
    events as specified in Spec 03 §4.3.
    """
    full_text = []
    buffer = ""
    in_thinking = False
    
    # Initial start event
    start_payload = {"session_id": session_id, "status": "generating"}
    if metadata:
        start_payload.update(metadata)
    yield format_sse_event(start_payload, event_type="start")

    try:
        async for raw_token in token_stream:
            full_text.append(raw_token)
            buffer += raw_token

            while buffer:
                if not in_thinking:
                    if "<deep_thinking>" in buffer:
                        pre, buffer = buffer.split("<deep_thinking>", 1)
                        if pre:
                            yield format_sse_event({"type": "token", "token": pre, "content": pre, "done": False}, event_type="token")
                        in_thinking = True
                    elif any("<deep_thinking>".startswith(buffer[i:]) for i in range(len(buffer))):
                        # Potential partial tag at tail; break to accumulate next token
                        break
                    else:
                        yield format_sse_event({"type": "token", "token": buffer, "content": buffer, "done": False}, event_type="token")
                        buffer = ""
                else:
                    if "</deep_thinking>" in buffer:
                        reasoning_chunk, buffer = buffer.split("</deep_thinking>", 1)
                        if reasoning_chunk:
                            yield format_sse_event({"type": "reasoning_delta", "token": reasoning_chunk, "content": reasoning_chunk, "done": False}, event_type="reasoning_delta")
                        in_thinking = False
                    elif any("</deep_thinking>".startswith(buffer[i:]) for i in range(len(buffer))):
                        # Potential partial closing tag at tail; wait for more
                        break
                    else:
                        yield format_sse_event({"type": "reasoning_delta", "token": buffer, "content": buffer, "done": False}, event_type="reasoning_delta")
                        buffer = ""

            # Yield control to event loop
            await asyncio.sleep(0.001)

        # Flush any remaining text in buffer
        if buffer:
            if in_thinking:
                yield format_sse_event({"type": "reasoning_delta", "token": buffer, "content": buffer, "done": False}, event_type="reasoning_delta")
            else:
                yield format_sse_event({"type": "token", "token": buffer, "content": buffer, "done": False}, event_type="token")

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

