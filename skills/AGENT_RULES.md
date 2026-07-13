# Agent Rules

If using Claude Code / an agent per person:

1. **Subtree Exclusive Boundaries**: Agent only touches files inside its owner's subtree unless the task is explicitly cross-cutting.
   - `backend/app/retrieval/*` = Person B (RAG core)
   - `backend/app/defense/*` = Person C (Defense & Security)
   - `frontend/*` = Person A (Frontend)
   - Exceptions: `schemas.py`, `main.py`, and `docker-compose.yml`, which require double review.
2. **Pre-Commit Verification**: Agent must run `pytest backend/tests -k <own module>` before proposing a commit.
3. **Commit Incrementality**: Agent commits in small units — one logical change per commit, using Conventional Commits format (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
4. **Contract Warnings**: Agent never edits `schemas.py` without flagging it in the PR description as "⚠️ contract change."
5. **Security Audits**: `skills/security-checklist.md` must be checked before every PR into `dev`.
