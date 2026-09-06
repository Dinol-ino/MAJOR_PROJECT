# Online/Offline Legal Research Subsystem (Phase 10)
from app.research.provenance import (
    ProvenanceRecord,
    LegalEvidenceItem,
    validate_provenance_completeness,
)
from app.research.source_validator import (
    SourceValidator,
    source_validator,
)
from app.research.freshness import (
    FreshnessDetector,
    FreshnessResult,
    freshness_detector,
)
from app.research.conflict_detector import (
    LegalConflictDetector,
    ConflictType,
    ConflictRecord,
    conflict_detector,
)
from app.research.pipeline import (
    LegalResearchPipeline,
    ResearchPipelineResult,
    research_pipeline,
)

__all__ = [
    "ProvenanceRecord",
    "LegalEvidenceItem",
    "validate_provenance_completeness",
    "SourceValidator",
    "source_validator",
    "FreshnessDetector",
    "FreshnessResult",
    "freshness_detector",
    "LegalConflictDetector",
    "ConflictType",
    "ConflictRecord",
    "conflict_detector",
    "LegalResearchPipeline",
    "ResearchPipelineResult",
    "research_pipeline",
]
