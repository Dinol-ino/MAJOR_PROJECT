import os
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

PROMPTS_DIR = os.path.dirname(os.path.abspath(__file__))


class PromptAssembler:
    """
    Versioned system prompt assembler.
    Composes the 6 versioned prompt markdown sections in strict, deterministic order.
    Enforces that security_core.md is immutable and cannot be overridden by request-time input.
    """

    def __init__(self, prompts_dir: Optional[str] = None):
        self.prompts_dir = prompts_dir or PROMPTS_DIR
        self._sections: Dict[str, str] = {}
        self._load_sections()

    def _load_sections(self):
        section_names = [
            "security_core",
            "legal_behavior",
            "retrieval_instructions",
            "tool_policy",
            "citation_requirements",
            "task_template",
        ]
        for name in section_names:
            file_path = os.path.join(self.prompts_dir, f"{name}.md")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    self._sections[name] = f.read().strip()
            else:
                logger.warning(f"Prompt section file not found: {file_path}. Using fallback.")
                self._sections[name] = f"# {name.upper()}"

    def get_immutable_security_core(self) -> str:
        """Returns the immutable security core prompt section."""
        return self._sections.get("security_core", "")

    def get_template(self) -> str:
        """
        Assembles all prompt sections in strict fixed order:
        1. security_core (IMMUTABLE)
        2. legal_behavior
        3. retrieval_instructions
        4. tool_policy
        5. citation_requirements
        6. task_template (with {context_data} and {question} placeholders)
        """
        ordered_parts = [
            self._sections.get("security_core", ""),
            self._sections.get("legal_behavior", ""),
            self._sections.get("retrieval_instructions", ""),
            self._sections.get("tool_policy", ""),
            self._sections.get("citation_requirements", ""),
            self._sections.get("task_template", ""),
        ]
        return "\n\n".join([part for part in ordered_parts if part])

    def assemble(self, question: str, context_data: str) -> str:
        """
        Assembles the complete final prompt with context and user question populated.
        """
        template = self.get_template()
        return template.format(
            context_data=context_data,
            question=question
        )


# Global singleton instance
prompt_assembler = PromptAssembler()
