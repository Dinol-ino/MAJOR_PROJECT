import os
import yaml
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict
from app.system.hardware_detector import HardwareProfile

logger = logging.getLogger(__name__)

@dataclass
class ModelEntry:
    model_id: str
    display_name: str
    provider: str
    size_gb: float
    ram_required_gb: float
    context_window: int
    quantization: str
    tier: str
    requires_avx2: bool = False
    vram_required_gb: Optional[float] = None
    language_support: Optional[List[str]] = None
    ollama_tag: Optional[str] = None
    hf_repo: Optional[str] = None
    gguf_filename: Optional[str] = None

class ModelRegistry:
    def __init__(self, yaml_path: Optional[str] = None):
        if yaml_path is None:
            # Default location: backend/data/model_registry.yaml
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            yaml_path = os.path.join(base_dir, "data", "model_registry.yaml")

        self.yaml_path = yaml_path
        self._entries: Dict[str, ModelEntry] = {}
        self.reload()

    def reload(self):
        self._entries.clear()
        if not os.path.exists(self.yaml_path):
            logger.warning(f"Model registry YAML file not found at {self.yaml_path}. Loading defaults.")
            self._load_fallback_defaults()
            return

        try:
            with open(self.yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            raw_models = data.get("models", [])
            for item in raw_models:
                entry = ModelEntry(
                    model_id=item["model_id"],
                    display_name=item["display_name"],
                    provider=item["provider"],
                    size_gb=float(item["size_gb"]),
                    ram_required_gb=float(item["ram_required_gb"]),
                    context_window=int(item["context_window"]),
                    quantization=item.get("quantization", "q4_k_m"),
                    tier=item.get("tier", "standard"),
                    requires_avx2=item.get("requires_avx2", False),
                    vram_required_gb=float(item["vram_required_gb"]) if item.get("vram_required_gb") else None,
                    language_support=item.get("language_support", ["en"]),
                    ollama_tag=item.get("ollama_tag"),
                    hf_repo=item.get("hf_repo"),
                    gguf_filename=item.get("gguf_filename")
                )
                self._entries[entry.model_id] = entry
            logger.info(f"Loaded {len(self._entries)} models into registry from {self.yaml_path}")
        except Exception as e:
            logger.error(f"Failed to parse model registry YAML ({e}). Using fallback defaults.")
            self._load_fallback_defaults()

    def _load_fallback_defaults(self):
        defaults = [
            ModelEntry(
                model_id="qwen2.5:3b",
                display_name="Qwen 2.5 3B",
                provider="ollama",
                size_gb=2.0,
                ram_required_gb=4.0,
                context_window=8192,
                quantization="q4_k_m",
                tier="minimum",
                ollama_tag="qwen2.5:3b"
            ),
            ModelEntry(
                model_id="qwen2.5:7b",
                display_name="Qwen 2.5 7B",
                provider="ollama",
                size_gb=4.7,
                ram_required_gb=8.0,
                context_window=8192,
                quantization="q4_k_m",
                tier="standard",
                ollama_tag="qwen2.5:7b"
            )
        ]
        for m in defaults:
            self._entries[m.model_id] = m

    def all_models(self) -> List[ModelEntry]:
        return list(self._entries.values())

    def get(self, model_id: str) -> Optional[ModelEntry]:
        return self._entries.get(model_id)

    def recommended_for(self, hw: HardwareProfile) -> List[ModelEntry]:
        # Filter logic:
        # 1. RAM available headroom check (85%)
        # 2. VRAM check if GPU available
        # 3. AVX2 support check
        valid = []
        ram_budget = hw.ram_available_gb * 0.85
        vram_budget = (hw.gpu_vram_gb * 0.85) if (hw.gpu_available and hw.gpu_vram_gb) else 0.0

        tier_order = {"premium": 4, "recommended": 3, "standard": 2, "minimum": 1}

        for model in self._entries.values():
            if model.requires_avx2 and not hw.supports_avx2:
                continue

            # If GPU is required for model, verify VRAM
            if model.vram_required_gb and model.vram_required_gb > vram_budget:
                continue

            # RAM requirement check
            if model.ram_required_gb > max(ram_budget, hw.ram_total_gb * 0.7):
                continue

            valid.append(model)

        # Sort by tier weight desc, context window desc
        valid.sort(
            key=lambda m: (tier_order.get(m.tier, 0), m.context_window, -m.size_gb),
            reverse=True
        )
        return valid if valid else list(self._entries.values())
