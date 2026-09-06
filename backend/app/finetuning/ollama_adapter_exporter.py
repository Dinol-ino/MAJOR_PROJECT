import os
import logging

logger = logging.getLogger(__name__)


class OllamaAdapterExporter:
    """
    Generates Ollama Modelfile to package trained LoRA adapter weights for local Ollama deployment.
    Supports dynamic base model mapping per PC specs (Tier 0: qwen2.5:3b, Tier 1: qwen2.5:7b/saullm:7b, Tier 2: qwen2.5:14b).
    """
    def __init__(self, base_model: str = "qwen2.5:7b", adapter_path: str = "./dfrag_lora_adapter"):
        self.base_model = base_model
        self.adapter_path = adapter_path

    def _resolve_adapter_target(self) -> str:
        # Check if adapter_path is a directory and find exact weight file
        if os.path.isdir(self.adapter_path):
            safetensors_file = os.path.join(self.adapter_path, "adapter_model.safetensors")
            bin_file = os.path.join(self.adapter_path, "adapter_model.bin")
            if os.path.exists(safetensors_file):
                return safetensors_file.replace("\\", "/")
            elif os.path.exists(bin_file):
                return bin_file.replace("\\", "/")
        return self.adapter_path.replace("\\", "/")

    def generate_modelfile(self, output_path: str = "./Modelfile") -> str:
        adapter_target = self._resolve_adapter_target()

        modelfile_content = f"""# DFrag Stage 5 Behavior-Tuned Legal Model
FROM {self.base_model}
ADAPTER {adapter_target}

# System Prompt Enforcement
SYSTEM "You are DFrag Enterprise Legal Assistant. Always ground answers strictly in retrieved context and cite statutory provisions using [Act Name, Section X]."

# Generation Parameters
PARAMETER temperature 0.1
PARAMETER top_p 0.9
PARAMETER stop "<|im_end|>"
"""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(modelfile_content)

        logger.info(f"Generated Ollama Modelfile targeting {adapter_target} for base model {self.base_model} at {output_path}")
        return output_path


