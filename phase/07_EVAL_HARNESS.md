# Eval Harness (Parallel Track — Start at Stage 1, Run Continuously)

Not a stage to complete once. Stand up a minimal version at Stage 1 and grow it alongside every other stage.

## 1. RAGAS suite (dev/CI only, never runtime)

| Metric | Tracks regression in |
|---|---|
| Faithfulness | Hallucination — the top-priority metric, watch trend over time not just latest run |
| Context precision | Stage 2 retrieval quality (BM25 caching, hybrid fusion) |
| Context recall | Stage 2 corpus completeness/currency |
| Answer relevancy | Generation quality independent of grounding |

- Judge LLM: local Ollama model, explicitly configured via RAGAS's custom LLM wrapper — never the default cloud judge. Confidential legal excerpts do not leave the machine during eval, same as production.
- If judge quality (3–5B) is a bottleneck, run judging with a larger local model on a dev machine only — it never ships, so it isn't bound by the Tier 0 floor.

## 2. Adversarial suite (from Stage 1)

- Every injection test case used to validate Stage 1's hard-gate behavior lives here too, run alongside RAGAS on the same CI trigger — so a retrieval change can be checked against "did this weaken injection defense" in the same pass, not a separate disconnected process.
- Include: known injection patterns, benign-but-suspicious phrasing (should NOT false-positive), context-embedded instructions in retrieved documents (tests context sanitization, not just query-side filtering).

## 3. Legal-accuracy test set (curated, not auto-generated)

- Question/ground-truth-citation pairs, reviewed by someone with legal domain familiarity — not engineering-generated paraphrases of retrieved chunks (that only tests self-consistency, not correctness).
- Spans: direct factual lookup, multi-hop reasoning across two provisions, "no answer exists in corpus" refusal cases, superseded-provision traps (does the system correctly exclude repealed law per Stage 2 item A4).
- Living document — grows as real usage or team testing surfaces new cases. Assign an owner.

## 4. Trigger and reporting

- Run on every PR touching retrieval, generation, or validation logic.
- Faithfulness and injection-defense scores tracked as trends across merges, not pass/fail-only — a slow decline across several merges is the signal to catch before it compounds.
- Fine-tuned model candidates (Stage 5) must clear this suite with no regression before shipping, per Stage 5's evaluation gate.

## 5. Separate: Playwright E2E (frontend regression, not this file's scope)

- Playwright is also used for UI/E2E testing of the Tauri/web frontend (session panel, citation rendering, voice input) — track this under Stage 6 tooling, distinct from both the corpus-scraping use (Stage 2) and this eval harness.
