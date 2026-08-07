import re

class ResponseFormatter:
    """
    Cleans, strips, and formats LLM output for frontend rendering.
    """
    def format(self, raw_answer: str) -> str:
        if not raw_answer:
            return ""

        # Normalize multiple trailing newlines
        cleaned = re.sub(r'\n{3,}', '\n\n', raw_answer.strip())

        # Strip any unescaped prompt leak artifacts if present
        cleaned = re.sub(r'\[SYSTEM INSTRUCTION\].*?\n', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'\[RETRIEVED KNOWLEDGE CONTEXT\].*?\n', '', cleaned, flags=re.DOTALL)

        return cleaned.strip()
