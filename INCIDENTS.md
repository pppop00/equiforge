---
schema_version: 1
description: Append-only log of past failure modes and the contract that prevents them. Frozen into meta/system_prompt.frozen.txt at session start, alongside MEMORY.md. Read PRE-RUN to avoid repeating; read POST-RUN (P_INCIDENT_POSTCHECK) before delivery as a final self-check.
---

# equiforge — INCIDENTS

This file is the project's institutional memory of failure. Each entry is a real incident that happened, the root cause, and the *load-bearing* rule that keeps it from happening again. Treat every entry as a hard constraint, not advice. If a new run hits a situation that smells like one of these, **stop and re-read the relevant entry before proceeding**.

**Format contract.** Append only. Never delete an incident — supersede it with a new entry that links back. Keep `id` monotonically increasing (`I-001`, `I-002`, …). Keep entries short: the *what / why / rule / detection* fields are load-bearing; everything else is optional context.

---

## I-001 — P0 interactive gate bypassed by inventing a default

- **Date observed:** seen multiple times across runs prior to 2026-05-02
- **Phase:** `P0_palette` (also possible at `P0_lang`, `P0_sec_email` — same failure mode)
- **What happened:** Orchestrator hit an interactive gate without a `USER.md` sticky and without an actual user reply, and instead of halting, it picked `palette = "default"` (or `report_language = "en"`) and proceeded. All six cards rendered with the wrong colour scheme; the entire EP pipeline had to re-run.
- **Root cause:** Conflating "auto mode is active" with "I am authorized to invent values for interactive gates." Interactive gates exist precisely *because* the answer is not derivable from the prompt or environment; auto mode does not waive that.
- **Rule (load-bearing):** For `P0_lang`, `P0_sec_email`, `P0_palette`, the only allowed `meta/gates.json -> source` values are `user_response`, `USER.md sticky`, plus the gate-specific extras whitelisted in each agent (`explicit_phrase` for language; `skipped` / `declined` for SEC email). Strings like `auto_mode_default`, `inferred_from_prompt`, `default`, `assumed`, or any free-form value not in the whitelist are P0 violations and the run is not deliverable. **Auto mode is not an override.** If neither a real user reply nor a sticky exists, halt and ask.
- **Detection:** `meta/gates.json` post-run review. Also enforced by `references/p0_gates.md` whitelist and the orchestrator's "halt and wait" wording in `agents/orchestrator.md`.
- **Related contract:** `MEMORY.md` §"P0 gates"; `SKILL.md` §"P0 gates"; `references/p0_gates.md`.

## I-002 — P5 locked HTML template skipped, simplified hand-written report emitted

- **Date observed:** seen on `RA_Capital_2026-05-01_*` (private investment manager) and at least one prior run
- **Phase:** `P5_html` (also implicates `P5_html_gate`, `P5_5_data_val`, `P6_pkg`)
- **What happened:** When issuer-level financial statements were unavailable (private fund / family office / non-public issuer), the report writer or orchestrator decided the locked template "did not apply," skipped `tools/research/extract_template.py`, hand-wrote a ~200-line summary HTML, fabricated a packaging profile (`institution_compat_no_secapi_no_cards` — not in the whitelist), and wrote `pass_with_scope_limitations` into `report_validation.txt`. Every layer of that chain was forbidden.
- **Root cause:** Misreading "data is thin" as "template doesn't apply." The locked template is **never** scope-conditional. Its job when data is thin is to *make the gaps legible*, not to disappear.
- **Rule (load-bearing):**
  - **Every** equiforge run — public, private, hedge fund, family office, government entity, anything — fills the same SHA256-pinned locked skeleton extracted via `tools/research/extract_template.py`. There is **no** institution-compatible / private-company / scope-limited / simplified bypass.
  - When issuer-level statements are unavailable, fill the locked sections with the best available proxies (AUM, strategy, top holdings, manager-level filings, peer macro) and label residual gaps inline.
  - `tools/research/validate_report_html.py` exit code is non-negotiable. Non-zero ⇒ discard HTML, rerun P5 from the extracted skeleton.
  - `report_validation.txt` top-line status is one of `pass | warn | critical`. `pass_with_scope_limitations`, `not_applicable`, `partial_pass` are fabrications.
  - `structure_conformance.json -> profile` must be one of the four `strict_*` profiles in `workflow_meta.json -> packaging_profiles`. Inventing profile names is a P6 violation.
- **Detection:** `tools/research/validate_report_html.py` (exit code), `tools/research/packaging_check.py` (profile/status validation), `P5_html_gate` retry loop. Now also enforced by `attackers/red_team_numeric.md` and `red_team_narrative.md` post-P5.5.
- **Related contract:** `MEMORY.md` §"Hard rules"; `SKILL.md` §"Hard floor"; `agents/orchestrator.md` §14; `references/phase_contract.md`.

---

## How this file is used

1. **Pre-run** (`P_INCIDENT_PRECHECK`, fires before `P0_intent`): the orchestrator reads this file end-to-end. For each incident, it ensures the corresponding rule is wired into the current plan. If a rule is unclear or the incident is novel-looking for the current target, the orchestrator notes it in `meta/run.jsonl` as `incident_precheck.acknowledged`.
2. **Post-run** (`P_INCIDENT_POSTCHECK`, fires after `P12_final_audit` and before `P_DB_INDEX`): the orchestrator re-reads this file and confirms each incident's detection signal is green for this run. Output: `validation/incident_postcheck.json` with one entry per incident (`status: pass | flagged`, plus evidence path).
3. **On new failure**: the user runs `/log-incident <one-line description>`. Claude pulls the latest `meta/run.jsonl`, the user's description, and any phase outputs; drafts a candidate entry; the user confirms; the entry is appended here as `I-NNN`.
