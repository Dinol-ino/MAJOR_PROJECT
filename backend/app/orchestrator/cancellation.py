import asyncio
import logging
from typing import Dict, Optional, Set
from app.db.engine import get_sync_session
from app.db.models import ResearchSession

logger = logging.getLogger(__name__)


class CancellationManager:
    """
    Manages user-initiated and timeout-initiated cancellations (Phase 09).
    Ensures in-flight research loops, tool calls, and partial writes to L5 research memory
    are safely terminated and marked incomplete/cancelled without orphaned state.
    """

    def __init__(self):
        # Map of request_id -> cancellation reason
        self._cancelled_requests: Dict[str, str] = {}
        # Map of request_id -> asyncio.Event
        self._events: Dict[str, asyncio.Event] = {}
        # Active registered request IDs
        self._active_requests: Set[str] = set()

    def register(self, request_id: str) -> None:
        """Registers a new in-flight research request."""
        self._active_requests.add(request_id)
        if request_id not in self._events:
            self._events[request_id] = asyncio.Event()

    def is_cancelled(self, request_id: str) -> bool:
        """Checks whether the specified request has been cancelled."""
        return request_id in self._cancelled_requests

    def cancel(self, request_id: str, reason: str = "User cancelled request") -> bool:
        """
        Triggers cancellation for the specified request.
        Marks any corresponding L5 research session as cancelled in durable memory.
        """
        self._cancelled_requests[request_id] = reason
        if request_id in self._events:
            self._events[request_id].set()

        logger.info(f"Research request '{request_id}' cancelled. Reason: {reason}")

        # Update L5 ResearchSession status in DB if exists
        try:
            with get_sync_session() as session:
                rec = session.query(ResearchSession).filter(ResearchSession.session_id == request_id).first()
                if rec:
                    rec.status = "cancelled"
                    session.commit()
        except Exception as exc:
            logger.debug(f"Could not update ResearchSession status in DB for {request_id}: {exc}")

        return True

    def unregister(self, request_id: str) -> None:
        """Unregisters a completed or terminated request to release memory."""
        self._active_requests.discard(request_id)
        self._events.pop(request_id, None)
        self._cancelled_requests.pop(request_id, None)

    def get_cancellation_reason(self, request_id: str) -> Optional[str]:
        """Returns the reason for cancellation, if any."""
        return self._cancelled_requests.get(request_id)


cancellation_manager = CancellationManager()
