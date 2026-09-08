# Module 3 — Hardware Engine & Model Registry: Verify Real, Then Fix

**Priority**: P1. You flagged this yourself: *"the citation graph, hardware engine and auto pull llm feature I'm not sure if its hardcoded or dynamic."* This module exists to answer that question with evidence, then fix what's actually broken.

---

## 3.1 The inconsistency across Img 1, 5, and 6 needs root-causing, not papering over

All three screenshots are the same `Hardware Engine` view, same session (same clock area, same `172.17.2.82:3000` host), yet:
- Img 1 & 5: CPU Processor stuck on "Detecting…", model list area empty or showing "Scanning hardware and evaluating tier models…"
- Img 6: CPU shows "4 Physical Cores / AMD Ryzen 5 7235HS", RAM shows "1.05 GB / 11.69 GB" with a "Low RAM - CPU Mode" warning, GPU shows "6 GB VRAM / NVIDIA GeForce RTX 3050 6GB Laptop GPU", and a 7-entry model list appears with sizes, min-RAM requirements, and "Auto-Pull" buttons — one model (`Gemma 2 2B`) tagged "ACTIVE".

This is either (a) a real async telemetry read that just takes several seconds and the earlier screenshots caught it mid-load with no loading skeleton — the more benign explanation — or (b) two different data paths, one live (CPU/RAM/GPU numbers) and one static (the model list, which per report.md §12 should come from `model_registry.yaml` mapped against detected tier). Given `Qwen 2.5 14B` is listed as "premium" tier and `Gemma 2 2B` as "ACTIVE" on a machine reporting only 11.69 GB total RAM and 6GB VRAM, the tier math needs checking too — report.md's own tier table (§12) puts Tier 1 (7B models) at 8–16GB, and this machine sits right at that boundary, so it's plausible but should be confirmed against the actual `HardwareTierClassifier` logic, not assumed correct because the UI renders confidently.

**Task 3.1.1** — Instrument `app/hardware/` (wherever CPU/RAM/GPU probing lives, per report.md §12: `winreg` for CPU, `psutil` for RAM, NVML for GPU) with explicit per-probe timing logs. Confirm whether the 8GB→11.69GB RAM discrepancy between Img 1/5 (both show "8 GB") and Img 6 ("11.69 GB") is a units/rounding difference (available vs. total) or a genuinely different read. Document the answer — don't just fix the UI to hide the discrepancy.

**Task 3.1.2** — Add a proper loading skeleton for the Hardware Engine view (ties into Module 5) so "Detecting…" never renders as a bare, ambiguous label with no spinner or timeout — currently indistinguishable from a hung request.

## 3.2 Verify Auto-Pull is real

**Task 3.2.1** — Trace `Auto-Pull` button in `HardwareForm.jsx`/model registry component to its backend call. It must hit Ollama's actual `/api/pull` endpoint (streaming progress, per Ollama's API) for the named model tag, and the model-registry entry's declared size (e.g. "4.7 GB" for `Qwen 2.5 7B`) must be validated against what Ollama actually reports for that tag — not a static number typed into `model_registry.yaml` by hand and never checked against reality.

**Task 3.2.2** — If Auto-Pull is currently a UI-only button with no backend wiring (plausible given the "not sure if it's hardcoded" framing), this is effectively defect #6 from your audit ("Only one small model (Gemma 2:2B) active despite a designed multi-tier model registry") re-confirmed. Fix: wire the button to real `ollama pull`, stream progress via SSE/WebSocket into the UI (the prior spec already asked for WebSocket/SSE hardware telemetry in its §4 — extend the same channel for pull progress rather than building a second one), and update `ACTIVE` status only after Ollama confirms the model is loaded and passes a real inference smoke-test (one throwaway prompt), not just after the download completes.

**Task 3.2.3** — `dfrag-legal:7b`, visible as the active model in Img 7's high-quality response, needs to be reachable from this same registry and pull flow — right now it appears to exist only when manually selected, not as a recommended/auto-pulled option in Img 6's list. If it's the fine-tuned model referenced in Stage 5 of your roadmap, it should be the top-recommended model for Tier 1 hardware once Stage 5 actually ships, not absent from the list.

## 3.3 Container-based execution, since you mentioned "gotta work with the containers"

**Task 3.3.1** — Confirm whether Ollama itself is expected to run in the Docker Compose `ollama` service (per report.md §17: "Managed Ollama service with persistent model store on port 11434") or on bare host Windows in your dev setup (the screenshots show `172.17.2.82:3000`, a LAN IP, suggesting the app may be running inside a container/VM already, separate from wherever Ollama lives). Model pull-and-persist behavior differs materially between these two setups — a pull into a container without a mounted volume for Ollama's model store is lost on container restart. Task: confirm the `ollama` service in `docker-compose.yml` has a named volume for its model directory, and that Auto-Pull writes there, not into ephemeral container storage.

## Acceptance criteria for Module 3
- [ ] Hardware telemetry read is single-sourced and consistent across repeated loads of the same view (no more Img1/5/6-style discrepancy).
- [ ] Auto-Pull demonstrably invokes real Ollama pull with visible progress and a post-pull inference smoke test, not a UI-only status flip.
- [ ] Model registry `ACTIVE` status reflects actual loaded-and-verified state, not "user clicked the model selector."
- [ ] Confirmed and documented: where Ollama's model store physically persists across restarts.
