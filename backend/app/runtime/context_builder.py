from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class ContextPackage:
    full_prompt: str
    token_count: int
    chunks_included: List[Dict[str, Any]]
    chunks_truncated: int

class ContextBuilder:
    """
    Assembles prompt context in strict priority order:
    1. System instructions
    2. Permanent User Profile & Matter context
    3. Conversation Summary
    4. Recent conversation history
    5. Retrieved knowledge chunks (Tier 1 Law + Tier 2 User)
    6. User query
    """

    def build(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        user_profile: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        summary: Optional[str] = None
    ) -> ContextPackage:

        sections = []

        # 1. System Instruction Block
        system_instr = (
            "You are a professional legal assistant for Indian Law. "
            "Answer accurately using ONLY the provided retrieved context chunks. "
            "If the context does not contain enough information, clearly state that information is unavailable."
        )
        sections.append(f"[SYSTEM INSTRUCTION]\n{system_instr}")

        # 2. Permanent User Profile & Matter Context
        if user_profile:
            lawyer_name = user_profile.get("display_name", "Practitioner")
            firm_name = user_profile.get("firm_name", "Legal Firm")
            matter_name = user_profile.get("matter_name", "General Matter")
            profile_block = (
                f"[USER PROFILE & MATTER CONTEXT]\n"
                f"Lawyer: {lawyer_name} ({firm_name})\n"
                f"Active Matter: {matter_name}"
            )
            sections.append(profile_block)

        # 3. Conversation Summary
        if summary:
            sections.append(f"[CONVERSATION SUMMARY]\n{summary}")

        # 4. Recent History (last 5 turns)
        if history:
            history_lines = []
            for item in history[-5:]:
                role = "User" if item.get("role") == "user" else "Assistant"
                content = item.get("content", "")
                history_lines.append(f"{role}: {content}")
            if history_lines:
                sections.append("[CONVERSATION HISTORY]\n" + "\n".join(history_lines))

        # 5. Retrieved Knowledge Chunks
        chunk_texts = []
        chunks_included = []
        for i, c in enumerate(retrieved_chunks):
            act = c.get("act", "General Law")
            sec = c.get("section", "Section N/A")
            text = c.get("text", "")
            chunk_texts.append(f"--- Chunk {i+1} [Act: {act}, Section: {sec}] ---\n{text}")
            chunks_included.append(c)

        if chunk_texts:
            sections.append("[RETRIEVED KNOWLEDGE CONTEXT]\n" + "\n\n".join(chunk_texts))
        else:
            sections.append("[RETRIEVED KNOWLEDGE CONTEXT]\nNo relevant legal chunks retrieved.")

        # 6. User Query
        sections.append(f"[USER QUESTION]\n{query}\n\n[ASSISTANT ANSWER]:")

        full_prompt = "\n\n".join(sections)
        # Approximate 4 chars per token estimation
        estimated_tokens = len(full_prompt) // 4

        return ContextPackage(
            full_prompt=full_prompt,
            token_count=estimated_tokens,
            chunks_included=chunks_included,
            chunks_truncated=0
        )
