import time
import logging
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)


class LimitExceeded(Exception):
    """Base exception raised when an orchestrator execution ceiling is breached."""
    def __init__(self, limit_type: str, current_value: Any, max_value: Any, message: Optional[str] = None):
        self.limit_type = limit_type
        self.current_value = current_value
        self.max_value = max_value
        self.message = message or f"Execution limit breached for '{limit_type}': current={current_value}, max_allowed={max_value}"
        super().__init__(self.message)


class StepLimitExceeded(LimitExceeded):
    """Raised when maximum steps per research request is exceeded."""
    def __init__(self, current_steps: int, max_steps: int):
        super().__init__("max_steps", current_steps, max_steps, f"Step limit exceeded: {current_steps}/{max_steps} steps taken.")


class ToolCallLimitExceeded(LimitExceeded):
    """Raised when maximum tool calls per request is exceeded."""
    def __init__(self, current_calls: int, max_calls: int):
        super().__init__("max_tool_calls", current_calls, max_calls, f"Tool call budget exceeded: {current_calls}/{max_calls} calls dispatched.")


class TokenLimitExceeded(LimitExceeded):
    """Raised when cumulative token budget is exceeded."""
    def __init__(self, current_tokens: int, max_tokens: int):
        super().__init__("max_tokens", current_tokens, max_tokens, f"Token ceiling exceeded: {current_tokens}/{max_tokens} tokens consumed.")


class TimeLimitExceeded(LimitExceeded):
    """Raised when execution wall-clock time limit is exceeded."""
    def __init__(self, elapsed_seconds: float, max_seconds: float):
        super().__init__("max_time_seconds", round(elapsed_seconds, 2), max_seconds, f"Execution time ceiling exceeded: {elapsed_seconds:.2f}s / {max_seconds}s.")


class DocLimitExceeded(LimitExceeded):
    """Raised when total retrieved documents ceiling is exceeded."""
    def __init__(self, current_docs: int, max_docs: int):
        super().__init__("max_retrieved_docs", current_docs, max_docs, f"Document retrieval ceiling exceeded: {current_docs}/{max_docs} documents.")


class NetworkLimitExceeded(LimitExceeded):
    """Raised when maximum network requests ceiling is exceeded."""
    def __init__(self, current_requests: int, max_requests: int):
        super().__init__("max_network_requests", current_requests, max_requests, f"Network request ceiling exceeded: {current_requests}/{max_requests} requests.")


class RetryBudgetExceeded(LimitExceeded):
    """Raised when step-level retry budget is exhausted."""
    def __init__(self, current_retries: int, max_retries: int):
        super().__init__("retry_budget", current_retries, max_retries, f"Retry budget exhausted: {current_retries}/{max_retries} attempts.")


class ExecutionBudget:
    """
    Tracks and enforces hard execution ceilings for a single research request.
    Reads defaults from centralized Settings.orchestrator.
    """

    def __init__(
        self,
        max_steps: Optional[int] = None,
        max_tool_calls: Optional[int] = None,
        max_tokens: Optional[int] = None,
        max_execution_time_seconds: Optional[float] = None,
        max_retrieved_docs: Optional[int] = None,
        max_network_requests: Optional[int] = None,
        retry_budget: Optional[int] = None,
    ):
        cfg = settings.orchestrator
        self.max_steps = max_steps if max_steps is not None else cfg.max_steps
        self.max_tool_calls = max_tool_calls if max_tool_calls is not None else cfg.max_tool_calls
        self.max_tokens = max_tokens if max_tokens is not None else cfg.max_tokens
        self.max_execution_time_seconds = max_execution_time_seconds if max_execution_time_seconds is not None else cfg.max_execution_time_seconds
        self.max_retrieved_docs = max_retrieved_docs if max_retrieved_docs is not None else cfg.max_retrieved_docs
        self.max_network_requests = max_network_requests if max_network_requests is not None else cfg.max_network_requests
        self.retry_budget = retry_budget if retry_budget is not None else cfg.retry_budget

        # Runtime counters
        self.steps_taken = 0
        self.tool_calls_made = 0
        self.tokens_used = 0
        self.docs_retrieved = 0
        self.network_requests_made = 0
        self.retries_attempted = 0
        self.start_time = time.time()

    def record_step(self) -> int:
        """Records a state machine transition step and checks ceilings."""
        self.check_time()
        self.steps_taken += 1
        if self.steps_taken > self.max_steps:
            raise StepLimitExceeded(self.steps_taken, self.max_steps)
        return self.steps_taken

    def record_tool_call(self) -> int:
        """Records an external/local tool dispatch and checks tool call budget."""
        self.check_time()
        self.tool_calls_made += 1
        if self.tool_calls_made > self.max_tool_calls:
            raise ToolCallLimitExceeded(self.tool_calls_made, self.max_tool_calls)
        return self.tool_calls_made

    def record_tokens(self, count: int) -> int:
        """Records cumulative prompt + generation tokens and checks token budget."""
        self.check_time()
        self.tokens_used += count
        if self.tokens_used > self.max_tokens:
            raise TokenLimitExceeded(self.tokens_used, self.max_tokens)
        return self.tokens_used

    def record_docs(self, count: int) -> int:
        """Records retrieved document chunks and checks document quota."""
        self.check_time()
        self.docs_retrieved += count
        if self.docs_retrieved > self.max_retrieved_docs:
            raise DocLimitExceeded(self.docs_retrieved, self.max_retrieved_docs)
        return self.docs_retrieved

    def record_network(self, count: int = 1) -> int:
        """Records an external HTTP or scrape network request."""
        self.check_time()
        self.network_requests_made += count
        if self.network_requests_made > self.max_network_requests:
            raise NetworkLimitExceeded(self.network_requests_made, self.max_network_requests)
        return self.network_requests_made

    def record_retry(self) -> int:
        """Records a step retry attempt and checks retry budget."""
        self.check_time()
        self.retries_attempted += 1
        if self.retries_attempted > self.retry_budget:
            raise RetryBudgetExceeded(self.retries_attempted, self.retry_budget)
        return self.retries_attempted

    def check_time(self) -> float:
        """Checks elapsed wall-clock execution time against the time ceiling."""
        elapsed = time.time() - self.start_time
        if elapsed > self.max_execution_time_seconds:
            raise TimeLimitExceeded(elapsed, self.max_execution_time_seconds)
        return elapsed

    def snapshot(self) -> Dict[str, Any]:
        """Returns a serializable dictionary of the current execution budget status."""
        return {
            "steps_taken": self.steps_taken,
            "max_steps": self.max_steps,
            "tool_calls_made": self.tool_calls_made,
            "max_tool_calls": self.max_tool_calls,
            "tokens_used": self.tokens_used,
            "max_tokens": self.max_tokens,
            "docs_retrieved": self.docs_retrieved,
            "max_retrieved_docs": self.max_retrieved_docs,
            "network_requests_made": self.network_requests_made,
            "max_network_requests": self.max_network_requests,
            "retries_attempted": self.retries_attempted,
            "retry_budget": self.retry_budget,
            "elapsed_seconds": round(time.time() - self.start_time, 3),
            "max_execution_time_seconds": self.max_execution_time_seconds,
        }
