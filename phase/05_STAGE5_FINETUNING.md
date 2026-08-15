# Stage 5 — LoRA Fine-Tuning (Behavior-Only, Deferred Until Stages 1–4 Are Stable)

## Hard scope boundary (read before doing anything else in this stage)

Fine-tuning in this project targets **model behavior only**: citation discipline, structured output conformance, refusal when context is absent. It **never** targets legal facts. Legal facts live permanently in retrieval (pgvector/BM25, Stage 2), versioned and updatable without retraining.

This boundary was violated in an earlier proposal (fine-tuning on updated legal PDFs directly) and rejected for these reasons, restated here so the boundary doesn't drift back:
- A fact fine-tuned into weights cannot be cited — breaks the citation-grounded requirement entirely.
- Weights don't update when the corpus is re-ingested (Stage 2, item B4) — creates silent staleness with no detection mechanism.
- If weights and retrieved context disagree, there's no principled way to know which the model will trust — introduces a second, hidden, unreconciled source of legal "fact."

**Do not fine-tune on legal PDF content under any framing in this stage.**

## 1. What this stage actually trains

Training examples are (context, query, ideal-answer) triples where the *content* varies but the *goal* is teaching the model to:
- Always produce the structured output schema (`answer`, `citations[]`, `confidence`) from Stage 1 item 9, even under adversarial or malformed context.
- Refuse cleanly and explicitly when retrieved context doesn't cover the query, rather than filling the gap from parametric knowledge.
- Correctly attribute citations to the specific chunk supporting each claim, not just append citations generically at the end.
- Handle multi-hop questions (answer requires combining two retrieved provisions) with both provisions cited, not just one.

The legal *content* in training examples should span real (already-ingested, versioned) corpus documents — but the model is not being taught new facts, it's being taught the *behavior pattern* using facts it will also encounter via retrieval at inference time. Prefer synthetic (context, query, answer) triples generated from the existing corpus + a stronger local or Colab-hosted model as a teacher, then reviewed, over any raw fine-tune of PDF text.

## 2. Pipeline (Colab, no local GPU required)

```
[Export (context, query, ideal-answer) training set — generated + reviewed, not raw PDFs]
  -> [Upload to Colab]
  -> [LoRA/QLoRA fine-tune on base Tier 1 model (e.g. Mistral-7B or SaulLM-7B)]
  -> [Evaluate against 07_EVAL_HARNESS.md suite BEFORE merging — must not regress faithfulness/citation accuracy vs. base model]
  -> [Export LoRA adapter]
  -> [Package for Ollama (adapter applied at load, or merged per Ollama's supported workflow)]
  -> [Ship as an optional upgrade per tier, not a forced replacement]
```

## 3. Evaluation gate (blocking)

- The fine-tuned model must be run through the full RAGAS + adversarial suite (`07_EVAL_HARNESS.md`) and must not regress faithfulness, context precision, or injection-resistance scores versus the un-tuned base model for the same tier.
- If it improves structured-output conformance but regresses faithfulness, it is not shipped — behavior gains do not offset accuracy losses.

## 4. Per-tier applicability

- Fine-tuning work in this stage should target the Tier 1 (7–8B) model first — it's the tier most likely to benefit from behavior shaping without already being capable enough (Tier 2) or too constrained to hold the adapter usefully (Tier 0).
- Tier 0 (3B) may get a separate, smaller-scope adapter later if the base model's structured-output failure rate (tracked via the Stage 1 validation-retry metric) justifies the effort — not assumed by default.

## Exit criteria for Stage 5
LoRA adapter exists, passes the evaluation gate with no regression on faithfulness/injection metrics, and is packaged for optional use — deferred entirely if Stages 1–4 are not yet stable per their own exit criteria.
