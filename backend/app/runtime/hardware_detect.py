from dataclasses import asdict
from typing import Dict, Any
from app.system.hardware_detector import HardwareDetector


def detect_hardware() -> Dict[str, Any]:
    """Runs automatic system hardware detection and returns a dictionary profile."""
    profile = HardwareDetector.detect()
    tier_info = HardwareDetector.get_auto_selected_tier(profile)
    specs = asdict(profile)
    specs.update(tier_info)
    return specs


def get_current_tier() -> str:
    """Returns the current recommended hardware tier: minimum, standard, premium."""
    tier_info = HardwareDetector.get_auto_selected_tier()
    num_tier = tier_info.get("tier", 0)
    if num_tier == 2:
        return "premium"
    elif num_tier == 1:
        return "standard"
    return "minimum"
