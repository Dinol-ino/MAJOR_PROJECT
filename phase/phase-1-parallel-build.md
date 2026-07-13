# Phase 1: Parallel Build (H1 - H7)

- **Owners**: Person A (Frontend), Sweedan (RAG Core), Dinol (Defense & Security)
- **Status**: Logic Implementation In Progress (Dinol complete, Sweedan pending)
- **Blocked-by**: Phase 0

## Sweedan: RAG Core & Ingestion
- `[ ]` Implement Section-Aware Metadata Extractor & Chunker (`chunker.py` & `pageindex.py`)
- `[ ]` Implement PDF secure reader with size validation limits (`pdf_extract.py`)
- `[ ]` Implement Tier-1 Law DB and Tier-2 User collections retrieval (`tier1_law.py` & `tier2_user.py`)
- `[ ]` Implement Reciprocal Rank Fusion BM25 + dense ranking logic (`hybrid_rank.py`)
- `[ ]` Implement database seeding logic parsing local acts text files (`seed_tier1.py`)
- `[ ]` Verify RAG retrieval logic via unit tests (`test_retrieval.py`)

## Dinol: Defense, Model & Logs
- `[x]` Implement Input Guard with length, jailbreak regex, and SQL probe regex (`layer1_input_guard.py`)
- `[x]` Implement Trusted Context prompt builder, wrapping data XML tags, and stripping instructions (`layer2_trusted_context.py`)
- `[x]` Implement Output Guard grounding overlap scorer, citation check, and system leak check (`layer3_output_guard.py`)
- `[x]` Implement SQLite database manager with SHA-256 hash chaining logging (`audit_log.py`)
- `[x]` Implement local Ollama API wrapper client with model fallback routing (`ollama_client.py`)
- `[x]` Implement hardware recommendation specs query matching (`recommend.py`)
- `[x]` Verify security logic layers via unit tests (`test_defense_layers.py`)

## Resumability Notes for Agents
- Dinol's backend files under `backend/app/defense/` and `backend/app/model/` are 100% complete and fully verified.
- The unit test suite (`test_defense_layers.py`) passes with OK status.
