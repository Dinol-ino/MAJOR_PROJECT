# Module 6 — Hardware, Model Registry, Runtime & MCP Endpoints: Purpose & Real Wiring

**Scope**: `app/routes/models.py`, `app/routes/recommend.py`, `app/routes/runtime.py`, `app/routes/mcp.py`, `GET /system/hardware`. Builds directly on Module 3's root-cause tasks — this file defines what each endpoint is *for*, so antigravity isn't just fixing bugs but understands the product reason each exists, which is what stops the next round of "looks done, isn't."

---

## 6.1 `GET /system/hardware` — purpose: tell the truth about what this machine can run

This single endpoint is the input to almost everything else in this module. Its only job is an honest, timestamped snapshot of CPU/RAM/GPU. It should never partially populate (Img 1/5's frozen "Detecting…" next to fully-populated RAM/GPU fields is a bug, not acceptable partial state) — either the whole probe returns together, or the UI shows a single unified loading state for the whole card, not per-field.

**Task 6.1.1**: Make this endpoint return all three probes (`winreg` CPU, `psutil` RAM, NVML GPU) as one atomic response with a `probed_at` timestamp, and have each individual probe fail independently into an explicit `null` + `reason` (e.g. `{"gpu": null, "reason": "no NVIDIA device found"}`) rather than letting one slow probe hold up the whole card indefinitely.

## 6.2 `GET /recommend` and `POST /recommend/override` — purpose: pick the best model *for this machine*, not a fixed default

**Purpose**: translate the 6.1 snapshot into a tier (0/1/2) and a ranked model recommendation, per the tier table already defined in report.md §12. This is a pure function of real hardware numbers — given the same CPU/RAM/GPU input, it must always produce the same tier. If Img 6's machine (4 cores, 11.69GB RAM, 6GB VRAM RTX 3050) is genuinely sitting at the Tier 0/Tier 1 boundary, the recommendation logic needs a documented tie-break rule (e.g. "VRAM governs over RAM when a discrete GPU is present"), not an implicit default that happens to match whatever model was last manually selected.

**Task 6.2.1**: `POST /recommend/override` exists so a user can manually pick a heavier model than recommended (accepting slower inference) — this must be a genuine override stored per-user/session, not silently reset on next hardware poll. Verify the "ACTIVE" badge on `Gemma 2 2B` in Img 6 reflects either a real recommendation or a real prior override, and expose which of the two it is in the UI (e.g. "Recommended for your hardware" vs. "Manually selected").

## 6.3 `GET /runtime/models` and `POST /models/pull` — purpose: the actual model inventory, not a wishlist

Per Module 3 §3.2: `POST /models/pull` must hit Ollama's real `/api/pull` and stream real progress. This section defines the *product* purpose of the 7-model list seen in Img 6 (`DFrag Legal 7B`, `SaulLM 7B`, `Llama 3.2 3B`, `Qwen 2.5 7B`, `Qwen 2.5 14B`, `Gemma 2 2B`, `Qwen 2.5 3B`): it is a **catalog of what the system supports pulling**, cross-referenced against **what's already pulled**, cross-referenced against **what's recommended for this hardware** — three different pieces of information currently collapsed into one undifferentiated list with one button style.

**Task 6.3.1**: Split the visual states clearly: `NOT_PULLED` (Auto-Pull button, greyed size/RAM info), `PULLING` (progress bar, cancel option), `PULLED_INACTIVE` (a "Switch To" button, not "Auto-Pull" — the download step is already done), `ACTIVE` (current badge, correctly used in Img 6 for Gemma 2 2B). Each state must be derived from actually querying Ollama's `/api/tags` for what's locally present plus the runtime manager for what's currently loaded — never inferred from "user clicked something once."

**Task 6.3.2**: `dfrag-legal:7b` (the fine-tuned model from Img 7's high-quality response) should appear in this same catalog once Stage 5 fine-tuning (per your roadmap) actually produces it, tagged distinctly (e.g. "Fine-tuned for Indian Law") from the general-purpose base models — this is the natural place to surface the payoff of the fine-tuning investment, rather than it existing as a manually-typed model string that bypasses the catalog entirely.

## 6.4 `GET /mcp/status`, `POST /mcp/tool-call`, `GET /mcp/history` — purpose: prove external legal sources are actually being consulted

This is the highest-priority item in this module given your explicit uncertainty ("not sure if it's hardcoded"). Per Img 2/5, the UI shows two "Registered MCP Servers" (`local-statute-server`, `indian-legal-gateway`) both marked "• Allowlisted," each with named `ALLOWED TOOLS` (`local_statute_search`, `local_provision_lookup`, `user_document_search` / `indiacode_fetcher`, `kanoon_case_search`, `live_statute_checker`).

**Task 6.4.1**: For each of the 5 named tools, confirm and document: (a) is there a real network client implementation behind it, (b) does it actually call an external service (India Code, Indian Kanoon) or a local stub, (c) what does `POST /mcp/tool-call` actually return today when invoked with each tool name. Do this by making direct calls (curl/Postman) against the running backend, bypassing the UI, and recording the raw response in this doc's companion evidence file. This directly answers your own question rather than assuming either way.

**Task 6.4.2** — if any tool is currently a stub: wire it for real, per the three MCP servers named in your own reference material (`ansvar-systems-india-law-mcp` for India Code central acts/DPDPA/IT Act/Companies Act/Consumer Protection Act; `Nyaya` for Constitution, BNS/BNSS/BSA, and Supreme Court judgments; `TaxByKK` for GST/indirect tax). These map cleanly onto the existing tool category taxonomy already defined in `mcp_permissions.yaml` (`LEGAL_SEARCH`, `CURRENT_LAW`, `CASE_LAW_SEARCH`, `GOVERNMENT_SOURCE`) — this is a wiring task against an existing, well-designed permission model, not a redesign.

**Task 6.4.3** — the "cloud dependency sitting alongside an OFFLINE badge" defect from your prior audit needs a specific fix here: if `indian-legal-gateway` requires outbound network access (it does, by definition — it's fetching from India Code/Kanoon), then invoking it must force-toggle the Mode Enforcer (report.md §11) to `ONLINE` for that call, with an explicit user-visible transition (not a silent exception to the OFFLINE badge). The OFFLINE badge must never be visibly "ON" while an outbound call is in flight — that's the exact confusability your audit flagged, and it's a trust-critical bug for a tool marketed on air-gapped confidentiality.

**Task 6.4.4** — `GET /mcp/history` should be genuinely queryable (not a static demo table) and cross-linked from the Cryptographic Audit Ledger (Module 8) — every MCP call is a security-relevant event and belongs in both views, sourced from the same underlying record, not two independently-maintained logs that can drift.

## 6.5 `GET /runtime/status`, `POST /runtime/switch`

**Purpose**: expose which backend (`OllamaRuntime`, `LlamaCppRuntime`, `MockRuntime`) is currently serving inference. **Critical flag**: `MockRuntime` existing as a documented, switchable runtime option (report.md §9 endpoint spec) is appropriate for automated tests, but `GET /runtime/status` must make it loudly, unmissably visible in the UI if `MockRuntime` is ever active outside a test environment — a user seeing Img 7-quality grounded responses while unknowingly talking to a mock runtime would be the single worst trust violation this product could commit. Add a hard runtime-environment check: `MockRuntime` should be unselectable via `POST /runtime/switch` outside of `pytest`/CI, enforced in code, not just by convention.

## Acceptance criteria for Module 6
- [ ] Hardware card renders as one atomic loading→populated transition, no more per-field inconsistency.
- [ ] Model list visually distinguishes not-pulled / pulling / pulled-inactive / active, each backed by a real Ollama query.
- [ ] Each of the 5 named MCP tools has a documented, verified real implementation (or is explicitly relabeled as not-yet-implemented in the UI until it is).
- [ ] Any ONLINE-mode MCP call visibly flips the mode badge for its duration; OFFLINE badge is never shown while outbound traffic is in flight.
- [ ] `MockRuntime` cannot be selected outside test environments, enforced in code.
