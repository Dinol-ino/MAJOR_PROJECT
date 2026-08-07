import re
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class HallucinationReport:
    signals: List[str]
    is_flagged: bool
    flagged_references: List[str]

class HallucinationDetector:
    """
    Lightweight, deterministic hallucination detection.
    Does NOT invoke secondary LLMs.
    """
    SECTION_REGEX = re.compile(r'(?:Section|Sec\.|Art(?:icle)?\.?)\s*(\d+[A-Z]?)', re.IGNORECASE)

    def detect(self, answer: str, chunks: List[Dict[str, Any]]) -> HallucinationReport:
        signals = []
        flagged_refs = []

        # Signal 1: Check cited sections in answer against retrieved context sections & chunk metadata
        cited_sections = set(self.SECTION_REGEX.findall(answer))

        # Build set of section numbers present in chunk texts and metadata fields
        context_sections = set()
        for c in chunks:
            sec_meta = str(c.get("section", ""))
            context_sections.update(self.SECTION_REGEX.findall(sec_meta))
            if sec_meta:
                # Direct match for simple numeric or alphanumeric section identifiers (e.g. "302", "420")
                context_sections.add(sec_meta.strip())
            
            text_val = c.get("text", "")
            context_sections.update(self.SECTION_REGEX.findall(text_val))

        for sec in cited_sections:
            if sec not in context_sections:
                signals.append("UNGROUNDED_SECTION_CITATION")
                flagged_refs.append(f"Section {sec}")

        # Signal 2: Context length gap (High output length with minimal context)
        context_words = sum(len(c.get("text", "").split()) for c in chunks)
        answer_words = len(answer.split())
        if answer_words > 300 and context_words < 100:
            signals.append("CONTEXT_LENGTH_GAP")

        return HallucinationReport(
            signals=list(set(signals)),
            is_flagged=len(signals) > 0,
            flagged_references=flagged_refs
        )
