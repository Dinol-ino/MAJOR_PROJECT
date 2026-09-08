# Module 1 — Grounding, Model Behavior & Response Professionalism

**Priority**: P0. Blocks all other modules. **Owner note**: this is not a fine-tuning problem primarily — it's a retrieval-coverage and failure-handling problem. Fine-tuning a 2–7B local model to be a better *writer* cannot fix answers that are wrong because the corpus behind them is thin (Img 8's ~14-node graph) or because the request path throws before generation even starts (Img 3).

---

## 1.1 Root-cause the Img 3 failure before touching prompts

Img 3 shows `GEMMA2:2B` returning `Error: Failed to fetch response from backend inference engine` / `Blocked by SYSTEM Guard: Failed to fetch` for the query *"What are the key provisions of Companies Act 2013 regarding director liability and fraud under Section 447?"* — a completely reasonable, non-adversarial legal question. This is not the injection gate correctly blocking an attack; the message text ("Failed to fetch") is a network/client error being mislabeled as a security block.

**Task 1.1.1** — In `app/security/injection_gate.py` (Layer 1) and whatever surfaces `SYSTEM Guard` text to the frontend: separate the three distinct failure classes that are currently collapsing into one red banner:
- Actual Layer 1 hard-gate rejection (adversarial input detected) → should show *why*, referencing the specific pattern category, not a generic label.
- Transport/connection failure (Ollama daemon unreachable, timeout) → should say "model temporarily unavailable" and trigger the Module 3 hardware-aware retry, never claim it was a security block.
- Retrieval returned zero or below-threshold results (see 1.2) → should say "no grounded source found" and trigger the refusal path, not throw.

**Task 1.1.2** — Add a correlation ID to every one of these three paths and require the frontend error component to render it, so you can trace any future "Failed to fetch" back to backend logs in seconds instead of guessing from a screenshot.

## 1.2 Implement the missing relevance threshold and refusal path (Defect #3)

Your prior audit confirmed there is no relevance threshold or refusal path — the system will answer even when retrieval returns nothing usable. This is the single highest-leverage fix for "hallucination" complaints, because most hallucination in a RAG system isn't the LLM inventing law from nothing — it's the LLM being handed irrelevant chunks and asked to synthesize an answer from them anyway.

**Task 1.2.1** — In the `EVIDENCE_VALIDATION` state of `app/orchestrator/state_machine.py` (step 7 in the documented FSM), add a hard numeric gate:
- Compute a relevance score per retrieved chunk from the RRF fusion output (you already compute RRF at k=60 per `report.md` §6 — reuse that score, don't add a second scoring system).
- If the top-N chunks all fall below a calibrated threshold (start at RRF score requiring chunk to be in top-3 of *both* BM25 and dense results, tune empirically against a labeled query set — see 1.5), transition to a new terminal state `INSUFFICIENT_EVIDENCE` instead of `SYNTHESIS`.
- `INSUFFICIENT_EVIDENCE` returns a fixed-format refusal: what was searched, why it came up short, and a suggestion (upload the relevant act, narrow the jurisdiction, rephrase). This is not the same as the Img 3 error — it's a correct, honest "I don't have this" answer, which is what a legal tool must be able to say.

**Task 1.2.2** — This directly fixes your audit's defect #1 (canned template responses to casual input presenting fake statutory retrieval) and defect #2 (non-legal ML papers cited as "Grounded Legal Sources") — both are symptoms of no threshold existing. Verify both are gone with a regression test: feed "hey there" (Img 3's own first message) and confirm the response is a polite scope statement, not a statute citation.

## 1.3 Corpus completeness — the actual lever for "not doing any better"

Per your own established principle: **broad coverage comes from corpus completeness, not fine-tuning.** Img 8's citation graph and Img 7's 5-citation response both draw from what your audit called a "~10-node seed citation graph rather than a real corpus." No amount of prompt engineering on `DFrag V4 Master System Prompt` fixes an answer about, say, the Motor Vehicles Act or a state-specific rent control act if that act was never ingested.

**Task 1.3.1** — Before any further UI work, get a real count: query ChromaDB and the BM25 index directly (`python -c` against `app/retrieval/...`) for total chunk count, distinct Acts covered, and distinct sections covered. Report this number. If it's still ~42 chunks (per the seed script `scripts/seed_tier1.py` referenced in report.md §17), corpus completeness is the actual blocker, not model choice.

**Task 1.3.2** — Build out `scripts/seed_tier1.py` into a real, resumable ingestion pipeline against India Code (via the `ansvar-systems-india-law-mcp` server once Module 4 confirms it's live) covering, at minimum: BNS 2023, BNSS 2023, BSA 2023, IT Act 2000 (full, not just §43/66/72A), Companies Act 2013 (full, not just director-liability sections), Contract Act 1872, Consumer Protection Act 2019, DPDPA 2023. Each Act should be ingested section-by-section with the 13-field provenance schema already designed in `app/research/provenance.py` — use what exists, don't redesign it.

**Task 1.3.3** — Add an ingestion completeness dashboard (feeds Module 5's UI work) so "how much law does this actually know" stops being an open question answerable only by screenshot inspection.

## 1.4 Response format professionalism

Img 7 is genuinely good and should be the template, not the exception: statutory analysis header, numbered breakdown per section, explicit "Legal Grounding & Compliance" statement, and a "Grounded Statutory Provisions & Citations" panel with per-citation provenance disclosure. The problem per your notes is that this quality is inconsistent — it appeared once, with `dfrag-legal:7b` active, and Img 3 shows the alternative (hard failure) with `gemma2:2b` active.

**Task 1.4.1** — Extract the response schema implicit in Img 7 into an explicit structured output contract (Pydantic model) that every model tier must fill, not just the fine-tuned 7B model: `{header, statutory_basis: [...], analysis_by_provision: [...], grounding_statement, citations: [...]}`. Enforce this at the Layer 3 Output Guard, not by hoping the prompt produces it — a 2B model under memory pressure (Tier 0, per report.md §12) needs the same structural guarantee a 7B model gets, even if the prose quality is lower. This is what makes the product feel non-"AI-generated" — structural consistency, not just better wording.

**Task 1.4.2** — The "Grounded (75%)" badge in Img 7 needs a defined, documented formula (currently opaque). Recommend: `grounded_pct = (claims with a citation whose token-overlap score exceeds gate threshold) / (total factual claims in response)`, computed by the existing Layer 3 token-overlap grounding logic (report.md §5) — expose the number it's already computing rather than inventing a new metric.

## 1.5 Where fine-tuning (Stage 5) actually helps, and where it doesn't

Consistent with your established principle — do not use fine-tuning to teach law. Use it only for:
- Enforcing the Task 1.4.1 structured output format under low-resource models (Tier 0/1) where prompting alone is unreliable.
- Citation discipline: refusing to state a legal conclusion without an attached citation.
- Refusal calibration: recognizing when to trigger `INSUFFICIENT_EVIDENCE` versus when retrieved evidence is thin-but-usable.

**Task 1.5.1** — Build the Stage 5 LoRA/QLoRA training set from real (query, retrieved-context, correct-structured-answer) triples generated *after* 1.2 and 1.3 land — training on today's thin corpus would bake in today's gaps as learned behavior, which is the exact anti-pattern the project's founding principles were written to prevent.

## Acceptance criteria for Module 1
- [ ] Img 3's failure mode reproduced and fixed: same query returns either a grounded answer or an honest `INSUFFICIENT_EVIDENCE` refusal, never a raw fetch error labeled as a security block.
- [ ] Chunk/Act/section coverage count reported and is materially larger than 42 chunks / ~14 graph nodes.
- [ ] "hey there" and other casual, non-legal input no longer produces fabricated statutory citations (defect #1/#2 closed, verified by regression test).
- [ ] Every model tier (0/1/2) returns the same structured response schema; only prose fluency varies.
- [ ] "Grounded (X%)" badge formula documented and traceable to Layer 3 code.
