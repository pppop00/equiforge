---
schema_version: 1
name: equity-fusion
description: |
  End-to-end skill: one prompt ("研究一下苹果" / "research Apple") drives the full pipeline —
  language gate, SEC email gate, palette gate, ER research (multi-agent), EP card generation,
  four-layer P12 audit (numerical reconcile + OCR + web third-check + DB cross-validation),
  and persistence into a local SQLite knowledge base for cross-quarter and cross-company reuse.
entry_point: agents/orchestrator.md
contract: workflow_meta.json
when_to_use: |
  Use this skill when a user wants a publishable equity research deliverable for one company —
  HTML report + 6 social cards + audited data — with the option to leverage prior runs of the
  same company or sector peers from the local DB.
requires_toolsets: ["research", "photo", "audit", "db", "web", "io"]
---

# Equity Fusion Skill

You are the orchestrator. Read this file once at session start, then read `MEMORY.md` and `USER.md` (if present), then read `agents/orchestrator.md` for the runtime brief.

## What this skill produces

For a prompt like **"研究一下苹果"** or **"research Apple"**, you produce one folder under `output/{Company}_{Date}_{RunID}/` containing:

| Subfolder | Contents |
|---|---|
| `meta/` | `run.jsonl` event log, `system_prompt.frozen.txt`, `gates.json`, `submodule_shas.json`, `workflow_meta.snapshot.json` |
| `research/` | All ER JSON artifacts + the locked-template HTML report (`{Company}_Research_{CN\|EN}.html`) + `cross_validation.json` + `report_validation.txt` + `structure_conformance.json` |
| `cards/` | `logo/{slug}_wordmark.png` + `{stem}.card_slots.json` + 6 PNGs (`01_cover.png` … `06_post_copy.png`) + Validator 1/2 reports |
| `validation/` | P12 four-layer audit: `post_card_audit.json`, `QA_REPORT.md`, `reconciliation.csv`, `ocr_dump/`, `web_third_check.json`, `db_cross.json` |
| `db_export/` | `rows_written.json`, `peer_context.json`, `prior_financials_used.json`, `db_index_summary.json` |
| `logs/` | `tools.jsonl` per-tool telemetry |

After the run, `db/equity_kb.sqlite` has new rows for this ticker + period that will be reused next quarter and made available as peer context for sibling companies.

## How to run

1. **Freeze the system prompt** — load `MEMORY.md` (project invariants) and `USER.md` (user preferences if present); record the resolved snapshot to `meta/system_prompt.frozen.txt`. Do not re-read these mid-run.
2. **Bootstrap the run dir** — call `tools/io/run_dir.py` to create `output/{Company}_{Date}_{RunID}/` and seed `meta/run.jsonl` with `phase: P0_intent, event: phase_enter`.
3. **Execute phases in order** per `workflow_meta.json`. For each phase:
   - Append `phase_enter` to `meta/run.jsonl`.
   - If the phase has a `tool`: invoke the Python script. If it has an `agent`: delegate to a fresh subagent context, scoped to the toolsets listed in the agent's frontmatter.
   - For `parallelism: parallel` phases, dispatch all listed agents simultaneously; respect `subagent_concurrency_cap` from `workflow_meta.json`.
   - On success: append `phase_exit` with the produced artifacts. On failure: append `phase_failed` with the error and follow the phase's `retry_to` / `retry_cap` policy.
4. **Stop and ask the user** at each `blocking: true, interactive: true` gate. Use the gate agent's prompt verbatim (in the user's language). Record the answer in `meta/gates.json` with `source: "user_response"` or `"USER.md sticky"`.
5. **Never skip P12** unless the user explicitly says so in the same turn. P12 is the paying-customer audit gate — its four layers (reconcile / OCR / web / DB) are described in `agents/post_card_auditor.md`.
6. **After P12 passes**, run `P_DB_INDEX` (`tools/db/index_run.py`) to write into the database. If P12 failed, surface the report and ask the user which upstream phase to re-run; do not write to DB.

## Subagent toolset whitelist

When delegating, restrict the child to the minimum toolsets needed:

| Subagent | Toolsets |
|---|---|
| `intent_resolver` | `web` |
| `language_gate`, `sec_email_gate`, `palette_gate` | `io` (only) |
| ER `financial_data_collector` | `research`, `web`, `io`, `db` (read) |
| ER `macro_scanner` | `research`, `web`, `io`, `db` (read for short-circuit) |
| ER `news_researcher` | `web`, `io`, `db` (read) |
| ER QC peers | `research`, `io`, `db` (read) |
| ER report writers | `research`, `io` |
| ER `final_report_data_validator` | `research`, `io` |
| EP `logo_production` | `web`, `io`, `photo` |
| EP `content_production`, `hardcode_audit`, `layout_fill` | `photo`, `io` |
| EP `validator_2` | `web`, `photo`, `io` |
| `post_card_auditor` | `audit`, `db` (read), `web`, `io` |
| `cross_validator` | `db` (read), `audit`, `io` |

## Reading order for a fresh session

1. This file (`SKILL.md`)
2. `MEMORY.md`
3. `USER.md` (if present)
4. `workflow_meta.json`
5. `agents/orchestrator.md`
6. The agent file for whatever phase you are about to enter

Do not pre-load the ER/EP submodule agent files — load them lazily when you delegate to them, so token cost scales with the actual phase being executed.

## Cross-quarter / cross-company

Before P1, the orchestrator runs `P0_DB_PRECHECK` (`tools/db/queries.py`):

- If `get_prior_financials(ticker, n=4)` returns rows → ER `financial_data_collector` is told "we have FY2025-FY2026Q1; only fetch the new period."
- If `get_macro_snapshot(geography, period)` returns a row collected in the last 14 days → `macro_scanner` short-circuits and reuses it.
- If `get_peer_companies(...)` returns ≥2 peers → P3.7_X_VALIDATE will run peer Porter divergence checks and P12 layer 4 will run DB cross-validation.

Cold start (no prior runs of anything) is handled gracefully: every read function returns empty list / None and the orchestrator skips the dependent checks with a note `status: "no_priors"` in the affected report.

## Maintenance

- When the locked HTML template inside `skills_repo/er/agents/report_writer_*.md` changes, the SHA256 in ER's `tests/test_extract_report_template.py` must be updated by the ER maintainer; this skill picks it up at the next `git submodule update`.
- When the EP card slot schema changes (`skills_repo/ep/references/card-slots.schema.json`), `tools/audit/reconcile_numbers.py` may need updated path mappings.
- When adding a new column to a DB table, write `db/schema/00X_*.sql` and bump `PRAGMA user_version`. Never destroy.

For the per-phase brief, open `agents/orchestrator.md`.
