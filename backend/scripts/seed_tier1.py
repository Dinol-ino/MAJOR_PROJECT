"""
CLI: index the local statutory corpus (data/acts_raw/*.txt described by manifest.yaml).

    python scripts/seed_tier1.py            # uses ACTS_RAW_DIR or the repo's data/acts_raw

Uses the same pipeline as the API (/statutes/sync); there is no separate seeding logic.
"""
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.statutory_corpus import index_statutory_corpus  # noqa: E402


def seed_database() -> dict:
    stats = index_statutory_corpus()
    print(json.dumps(stats, indent=2))
    if stats["unverified_acts"]:
        print(
            "\nNOTE: these acts have no verification date in manifest.yaml and are shown as UNVERIFIED:\n  - "
            + "\n  - ".join(stats["unverified_acts"])
        )
    return stats


if __name__ == "__main__":
    seed_database()
