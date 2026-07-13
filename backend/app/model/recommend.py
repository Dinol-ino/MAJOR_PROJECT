from typing import List, Dict

# Hardcoded model recommendations by hardware
MODEL_RECOMMENDATIONS = [
    {"model": "qwen2.5:3b", "size_q4": "~2.2 GB", "min_ram_gb": 8, "good_for": "Default; strong reasoning for size", "pull": "ollama pull qwen2.5:3b"},
    {"model": "phi3.5", "size_q4": "~2.4 GB", "min_ram_gb": 8, "good_for": "Strong instruction-following", "pull": "ollama pull phi3.5"},
    {"model": "llama3.2:3b", "size_q4": "~2.0 GB", "min_ram_gb": 8, "good_for": "Balanced, well-supported", "pull": "ollama pull llama3.2:3b"},
    {"model": "gemma2:2b", "size_q4": "~1.7 GB", "min_ram_gb": 6, "good_for": "Lightest, weakest hardware", "pull": "ollama pull gemma2:2b"},
    {"model": "mistral", "size_q4": "~4.4 GB", "min_ram_gb": 16, "good_for": "Best quality if hardware permits", "pull": "ollama pull mistral"}
]

def get_recommendation(ram_gb: int, vram_gb: int) -> List[Dict[str, str]]:
    total_mem = ram_gb + vram_gb
    if total_mem < 8:
        return [r for r in MODEL_RECOMMENDATIONS if r["model"] == "gemma2:2b"]
    elif total_mem >= 16:
        return [r for r in MODEL_RECOMMENDATIONS if r["model"] == "mistral"]
    else:
        # Default middle tier recommendations
        return [r for r in MODEL_RECOMMENDATIONS if r["model"] in ("qwen2.5:3b", "phi3.5", "llama3.2:3b")]
