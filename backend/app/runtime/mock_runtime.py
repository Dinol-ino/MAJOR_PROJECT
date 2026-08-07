import logging
from typing import Optional, AsyncIterator

logger = logging.getLogger(__name__)

class MockRuntime:
    def __init__(self, reply: str = "Mocked enterprise response"):
        self.reply = reply

    async def generate(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        return self.reply

    async def generate_stream(self, prompt: str, model: Optional[str] = None, **kwargs) -> AsyncIterator[str]:
        words = self.reply.split(" ")
        for w in words:
            yield w + " "

    async def health_check(self) -> bool:
        return True
