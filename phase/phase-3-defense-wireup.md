# Phase 3: Defense Wire-up (H9 - H12, All)

- **Owners**: Person A (Frontend), Sweedan (RAG Core), Dinol (Defense & Security)
- **Status**: Not Started
- **Blocked-by**: Phase 2

## Task Checklist
- `[ ]` [Dinol] Integrate the three defense layers (Input Guard, Trusted Context, Output Guard) into the core FastAPI `/chat` query processing logic.
- `[ ]` [Person A] Connect the UI Security Shield toggle switch to active backend requests (passing `shield_on` parameter).
- `[ ]` [Dinol] Run the automated security evaluation comparison script (`run_comparison.py`) and log output results.
- `[ ]` [Sweedan] Verify Tier-2 session context isolation (PDF uploaded in session A cannot be retrieved/leaked to session B).

## Resumability Notes for Agents
- If quota is completed mid-task, detail block-rate results here for the next agent session.
