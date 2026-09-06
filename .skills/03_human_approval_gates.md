# Agent Skill 03 — Human Approval Gates

Applies to: the specific actions below, across all phases. Stop and ask before proceeding on any of these — regardless of how confident the agent is, and regardless of what a phase file's implementation steps seem to imply. Most decisions should be made autonomously with a documented assumption (per `00_operating_principles.md` §7); these are the exceptions.

## The list

1. **Any destructive database operation** — dropping a table, removing SQLite as a fallback path, an irreversible migration. Confirm a backup/rollback path exists and get explicit go-ahead first.

2. **Which external legal sources are cleared for scraping** (`stages_2/02` item B1, `phase/10`'s allowlist). This was already flagged as a standing human decision — checking a site's current terms of service is not something to resolve by assumption, and the allowlist (`legal_sources.yaml`) should not be populated with a new domain without this check happening first.

3. **Accepting model licenses or gated Hugging Face terms.** Surface the requirement, don't click through it.

4. **Any change to the hard-gate security threshold, or disabling a defensive layer** — even temporarily, even for a single debugging session.

5. **Changing the default network mode away from OFFLINE**, or any change that would make ONLINE mode the default rather than an explicit opt-in.

6. **Adding a new third-party dependency** not already listed in `stages_2/09_PREREQUISITES.md` or named in the current phase's "Files to Add."

7. **Any production/release action** (`phase/16`'s gate). The agent runs the checklist and reports results — shipping is a human decision, not something the gate passing automatically triggers.

8. **Modifying `security_core.md`** (the immutable system-prompt section, `phase/01`). This section is deliberately unmodifiable by design. If a phase seems to require changing it, that itself is a signal something is off — stop and confirm rather than editing it.

9. **Any fine-tuning that would encode legal facts into model weights.** Per `stages_2/05`'s explicit rejection reasoning — if a task starts to look like "fine-tune on this legal PDF content," stop; this is out of scope regardless of how the request is framed.

10. **Removing or significantly restructuring code the audit couldn't verify as safe to remove** — if Phase 00's manifest marks something PARTIAL or unclear and a later phase's cleanup would delete it, confirm it's genuinely obsolete first rather than assuming Phase 00's uncertainty resolves in favor of deletion.

## How to ask

State plainly: what the action is, why it's on this list, what you'd do by default if approved, and what happens if you don't get approval (usually: skip this step, flag it, continue with the rest of the phase where possible). Don't let a pending approval silently block unrelated work in the same phase if it can proceed independently.
