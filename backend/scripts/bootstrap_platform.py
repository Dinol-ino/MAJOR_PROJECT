from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_ROOT))

from app.platform.bootstrap import ensure_database_exists, run_migrations


def main() -> None:
    created = ensure_database_exists()
    run_migrations()

    if created:
        print("Platform foundation bootstrap completed. Database created and migrations applied.")
    else:
        print("Platform foundation bootstrap completed. Database already existed; migrations applied.")


if __name__ == "__main__":
    main()
