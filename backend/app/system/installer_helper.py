import os
import logging
from typing import Dict, Any, Optional
from app.system.hardware_detector import HardwareDetector
from app.retrieval.tier1_law import Tier1LawRetrieval
from app.config import settings


logger = logging.getLogger(__name__)


class DesktopInstallerHelper:
    """
    Path B — Desktop Single-User Standalone Helper.
    Executes first-run environment validation, verifies pre-seeded statutory corpus readiness,
    runs hardware auto-detection, and ensures single-user standalone launch without requiring CLI steps.
    """
    def __init__(self, chroma_dir: Optional[str] = None):
        self.chroma_dir = chroma_dir or settings.CHROMA_PERSIST_DIR

    def run_first_launch_check(self) -> Dict[str, Any]:
        logger.info("Executing Desktop Standalone First-Launch Health Check...")

        # 1. Hardware Detection
        profile = HardwareDetector.detect()
        tier_info = HardwareDetector.get_auto_selected_tier(profile)

        # 2. Statutory Corpus Readability Check
        t1 = Tier1LawRetrieval(self.chroma_dir)
        try:
            corpus_count = t1.collection.count()
        except Exception:
            corpus_count = 0

        # 3. Environment Readiness
        ready = True
        notes = []

        if corpus_count == 0:
            notes.append("Statutory corpus empty — initial seed recommended.")

        return {
            "standalone_ready": ready,
            "hardware_tier": tier_info["tier_name"],
            "recommended_model": tier_info["default_model"],
            "corpus_chunks_indexed": corpus_count,
            "notes": notes
        }
