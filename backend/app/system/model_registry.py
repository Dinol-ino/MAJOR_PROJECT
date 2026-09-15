import os
import yaml
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
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
            # Primary location: backend/app/config/model_registry.yaml
            config_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            candidate = os.path.join(config_dir, "config", "model_registry.yaml")
            if os.path.exists(candidate):
                yaml_path = candidate
            else:
                base_dir = os.path.dirname(config_dir)
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

    def evaluate_model_fit(self, model: ModelEntry, hw: HardwareProfile) -> Dict[str, Any]:
        """
        Dynamically computes model safety & fit per Spec 00:
        - RAM limit: model must fit in 60% of available RAM (headroom for OS + ChromaDB + embedding)
        - VRAM limit: model must fit in 80% of detected VRAM (overhead for driver + KV cache)
        - Storage limit: model download size * 2 must be less than free disk space
        """
        ram_budget = hw.ram_available_gb * 0.60
        vram_budget = (hw.gpu_vram_gb * 0.80) if (hw.gpu_available and hw.gpu_vram_gb) else 0.0
        storage_required = model.size_gb * 2.0
        fits_storage = hw.storage_free_gb >= storage_required

        fits_vram = False
        if hw.gpu_available and vram_budget > 0 and model.vram_required_gb:
            fits_vram = model.vram_required_gb <= vram_budget

        fits_ram = model.ram_required_gb <= ram_budget

        if fits_vram:
            safety_tier = "SAFE"
            fit_reason = f"Fits in dedicated VRAM ({model.vram_required_gb or model.size_gb} GB <= {vram_budget:.1f} GB usable VRAM)"
        elif fits_ram:
            safety_tier = "SAFE"
            fit_reason = f"Fits in available RAM ({model.ram_required_gb} GB <= {ram_budget:.1f} GB usable RAM)"
        elif hw.gpu_available and model.vram_required_gb and model.vram_required_gb <= hw.gpu_vram_gb:
            safety_tier = "CAUTION"
            fit_reason = f"High VRAM pressure ({model.vram_required_gb} GB requires >80% of {hw.gpu_vram_gb} GB VRAM)"
        elif model.ram_required_gb <= hw.ram_available_gb:
            safety_tier = "CAUTION"
            fit_reason = f"High RAM pressure ({model.ram_required_gb} GB requires >60% of available RAM)"
        else:
            safety_tier = "UNSUPPORTED"
            fit_reason = f"Exceeds memory capacity (Requires {model.ram_required_gb} GB RAM / {model.vram_required_gb or 0} GB VRAM)"

        return {
            "fits_memory": fits_vram or fits_ram,
            "fits_vram": fits_vram,
            "fits_ram": fits_ram,
            "fits_storage": fits_storage,
            "safety_tier": safety_tier,
            "fit_reason": fit_reason
        }

    def recommended_for(
        self,
        hw: HardwareProfile,
        hard_max_ram_gb: Optional[float] = None,
        safe_only: bool = False
    ) -> List[ModelEntry]:
        """
        Ranks models based on dynamic hardware fit, legal specialization, and hardware tier.
        Enforces hard ceilings when hard_max_ram_gb or safe_only is specified.
        """
        tier_order = {"standard": 3, "recommended": 3, "premium": 2, "minimum": 1}
        models = list(self._entries.values())
        filtered = []

        max_ram = hard_max_ram_gb or (hw.ram_available_gb * 0.70)
        has_gpu = hw.gpu_available and bool(hw.gpu_vram_gb)

        for m in models:
            fit = self.evaluate_model_fit(m, hw)
            # If model does not fit in VRAM and exceeds hard max RAM, filter out if requested
            if not fit["fits_vram"] and m.ram_required_gb > max_ram:
                if safe_only:
                    continue
            if safe_only and fit["safety_tier"] == "UNSUPPORTED":
                continue
            filtered.append(m)

        def score_model(m: ModelEntry) -> float:
            fit = self.evaluate_model_fit(m, hw)
            score = tier_order.get(m.tier, 1) * 10.0

            # Safety tier weighting
            if fit["safety_tier"] == "SAFE":
                score += 15.0
            elif fit["safety_tier"] == "CAUTION":
                score += 5.0
            else:
                score -= 10.0

            # Legal specialization bonus
            if "legal" in m.model_id.lower() or "saullm" in m.model_id.lower() or "dfrag" in m.model_id.lower():
                score += 8.0

            return score

        filtered.sort(key=score_model, reverse=True)
        return filtered

