import os
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class BehaviorDatasetGenerator:
    """
    Generates synthetic behavior-only training triples (context, query, ideal_answer) for QLoRA fine-tuning.
    Hard Boundary: Never fine-tunes on raw legal facts directly. Focuses exclusively on:
    1. Structured citation formatting [Act, Section]
    2. Explicit refusal when retrieved context does not contain answer
    3. Multi-provision attribution
    """
    def __init__(self):
        pass

    def generate_sample_triples(self) -> List[Dict[str, Any]]:
        return [
            # Sample 1: Standard Grounded Citation
            {
                "instruction": "Answer the query using ONLY the provided legal context. Cite every statutory claim using [Act Name, Section X].",
                "context": "<data act='IT Act 2000' section='66'>Section 66: Computer Related Offences. If any person dishonestly or fraudulently does any act referred to in section 43, he shall be punishable with imprisonment for a term which may extend to three years or with fine which may extend to five lakh rupees or with both.</data>",
                "query": "What is the penalty for computer related offences under the IT Act?",
                "ideal_answer": "Under [IT Act 2000, Section 66], any person who dishonestly or fraudulently commits computer related offences shall be punished with imprisonment extending up to three years, or a fine up to five lakh rupees, or both."
            },
            # Sample 2: Context Absent -> Clean Refusal
            {
                "instruction": "Answer the query using ONLY the provided legal context. If the context does not contain sufficient information, explicitly refuse.",
                "context": "<data act='Motor Vehicles Act' section='112'>Section 112: Speed limits. No person shall drive a motor vehicle in any public place at a speed exceeding the maximum speed limit specified for the vehicle.</data>",
                "query": "What is the penalty for copyright infringement under legal provisions?",
                "ideal_answer": "I cannot answer this query based on the provided context. The retrieved legal provisions cover speed limits under the Motor Vehicles Act, but do not contain information regarding copyright infringement penalties."
            },
            # Sample 3: Multi-Provision Attribution
            {
                "instruction": "Answer the query using ONLY the provided legal context. Cite all supporting provisions.",
                "context": "<data act='IT Act 2000' section='43'>Section 43: Penalty and compensation for damage to computer system without permission.</data>\n<data act='IT Act 2000' section='66'>Section 66: Computer Related Offences. Dishonest acts under Section 43 are punishable under Section 66.</data>",
                "query": "How are unauthorized computer access and penalty linked under the IT Act?",
                "ideal_answer": "Unauthorized access to a computer system is governed by [IT Act 2000, Section 43]. If such acts are committed dishonestly or fraudulently, they become punishable offences under [IT Act 2000, Section 66]."
            }
        ]

    def export_jsonl(self, output_path: str, num_repeats: int = 1) -> str:
        """
        Exports the dataset into JSONL format (standard ChatML format for SFTTrainer/Unsloth).
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        samples = self.generate_sample_triples()

        with open(output_path, "w", encoding="utf-8") as f:
            for _ in range(num_repeats):
                for s in samples:
                    formatted_chatml = {
                        "messages": [
                            {"role": "system", "content": s["instruction"]},
                            {"role": "user", "content": f"Context:\n{s['context']}\n\nQuestion: {s['query']}"},
                            {"role": "assistant", "content": s["ideal_answer"]}
                        ]
                    }
                    f.write(json.dumps(formatted_chatml) + "\n")

        logger.info(f"Exported behavior training dataset ({len(samples) * num_repeats} samples) to {output_path}")
        return output_path
