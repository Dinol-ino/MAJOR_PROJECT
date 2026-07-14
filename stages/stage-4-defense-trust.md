# Stage 4: Defense and Trust Scoring

## Objective

Upgrade the current three-layer defense from mostly rule-based protection to a measured trust pipeline without losing the deterministic fail-closed behavior already present in the repo.

## Target state

- Layer 1 remains cheap and deterministic for obvious attacks.
- A `LegalBERT` classifier is added as a second signal before retrieval.
- Layer 2 still constructs trusted context boundaries.
- Retrieved chunks receive trust metadata before they reach generation.

## Defense architecture

### Layer 1

- length limits
- rate limits
- regex and policy checks
- basic unsafe prompt patterns

### Layer 1.5 classifier

- `LegalBERT` predicts `safe`, `suspicious`, or `malicious`
- classifier result does not replace deterministic rules
- classifier output feeds the policy engine

### Layer 2 trusted context

- strip embedded instructions
- wrap content in explicit data boundaries
- pass chunk metadata and trust fields forward

## Trust scoring fields

Each chunk should carry:

- `similarity_score`
- `trust_score`
- `freshness_score`
- `injection_risk_score`
- `confidence_score`

## Initial weighting to evaluate

- similarity: 40
- trust: 30
- injection risk: 20
- freshness: 10

## Required installs

- approved `LegalBERT` checkpoint
- model runtime support for the classifier

## Required `.env` values

- `INJECTION_MODEL`
- `INJECTION_BLOCK_THRESHOLD`
- `INJECTION_REVIEW_THRESHOLD`
- `TRUST_WEIGHT_SIMILARITY`
- `TRUST_WEIGHT_SOURCE`
- `TRUST_WEIGHT_INJECTION`
- `TRUST_WEIGHT_FRESHNESS`

## In scope

- classifier placement
- trust-score contract
- fail-closed policy rules
- chunk-level risk propagation

## Out of scope

- answer generation runtime swap
- PII redaction
- Langfuse dashboards

## Important rule

Do not let the classifier become the only gate. The current regex/rule layer is cheap and explainable. Keep both.

## Exit criteria

- Query screening is no longer regex-only.
- Retrieval outputs carry trust metadata.
- The trusted-context layer remains the explicit boundary between retrieved data and model instructions.
