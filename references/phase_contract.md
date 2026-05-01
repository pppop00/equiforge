---
schema_version: 1
description: Prose explanation of the 12-phase pipeline — what each phase does, what blocks, what runs in parallel, where outputs land. Read this for the phase narrative; read workflow_meta.json for the machine-readable contract.
---

# Phase contract

`workflow_meta.json` is the source of truth for phase IDs, tools, agents, parallelism, retry policies, and produced artifacts. This file is the prose companion: it explains *why* each phase exists and how it connects to the next.

For runtime procedure (the orchestrator's step-by-step), see `agents/orchestrator.md`. This file is for understanding the pipeline shape.

## The 12 phases at a glance

```
P0_intent → P0_lang → P0_sec_email → P0_palette → P0M_meta → P0_DB_PRECHECK
  → P1 parallel research (financial / macro / news, 3 subagents)
  → P1.5 edge insight
  → P2 financial analysis
  → P2.5 prediction waterfall
  → P2.6 macro QC peer A/B (parallel)
  → P3 Porter analysis
  → P3.5 Porter QC peer A/B (parallel)
  → P3.6 QC resolution merge
  → P3.7 cross-validation (history / peer / macro drift)
  → P4 Sankey payload
  → P5 HTML report writer (locked SHA256-pinned template)
  → P5.5 final data validator (CFA-level)
  → P6 report validator + packaging profile
  → P7 logo production (≥840px wide; saved to output dir first)
  → P8 card content production
  → P8.5 hardcode/logic audit
  → P9 layout fill (char/pixel budgets)
  → P10 Validator 1 (tools/photo/validate_cards.py)
  → P10.5 Validator 2 (web fact-check; loops back to P10 ≤3×)
  → P11 render 6 PNGs (2160×2700)
  → P12 final audit: reconcile + OCR + web third + DB cross  ★ paying-customer gate
  → P_DB_INDEX writes everything into db/equity_kb.sqlite
```

## P0 block — gates and bootstrap

| Phase | Purpose |
|---|---|
| `P0_intent` | Resolve `{ticker, company, listing}`. See `references/p0_gates.md`. |
| `P0_lang` | `report_language ∈ {en, zh}`. Blocking. |
| `P0_sec_email` | SEC EDGAR `User-Agent` email if US-listed mode A. Blocking. |
| `P0_palette` | One of `{macaron, default, b, c}`. Blocking. |
| `P0M_meta` | Validate `workflow_meta.json` schema (`tools/research/validate_workflow_meta.py`). |
| `P0_DB_PRECHECK` | Lookups for prior financials, peer companies, fresh macro snapshot. Never blocks. See `references/cross_quarter.md`. |

## P1–P3.7 — research pipeline (ER)

Delegated to subagents under `skills_repo/er/agents/`. The orchestrator's job is to dispatch with the right inputs (e.g., pass `prior_financials_used.json` to `financial_data_collector` so it knows which periods are already covered).

- **P1** is parallel: `financial_data_collector` ‖ `macro_scanner` ‖ `news_researcher` (concurrency 3).
- **P2.6** and **P3.5** are parallel pairs of QC peer agents.
- **P3.6** merges QC verdicts. Apply the scoring math from `MEMORY.md` exactly: `weighted = 0.34·draft + 0.33·a + 0.33·b`; only change scores when `|weighted − draft| > 1.00`.
- **P3.7** is `agents/cross_validator.md` + `tools/audit/db_cross_validate.py`. CRITICAL findings (self-history YoY mismatch >5pp; sector_macro_identity in mode A) block the next phase.

## P4–P6 — report writing (ER)

- **P4**: inject Sankey payload into `financial_analysis.json`.
- **P5**: extract the locked HTML skeleton via `tools/research/extract_template.py --lang <cn|en> --run-dir <run_dir> --sha256`. Delegate to `report_writer_{cn,en}.md`. **Never edit structure** — substitute `{{PLACEHOLDER}}` only.
- **P5_gate**: run `tools/research/validate_report_html.py --run-dir <run_dir> --lang <cn|en>`. It blocks simplified hand-written HTML by checking locked-template markers, six required sections, chart JS variables, minimum size/line count, and unresolved placeholders. Failure → discard the HTML and rerun P5 from the extracted skeleton.
- **P5.5**: `final_report_data_validator.md`. CRITICAL → loop back to P5 (cap 2). 0 CRITICAL → proceed.
- **P6**: `tools/research/packaging_check.py` + `report_validator.md`. `packaging_check.py` repeats the P5 HTML gate and stores `html_template_gate` in `structure_conformance.json`. Selects packaging profile from `strict_18_full_qc_secapi`, `strict_17_full_qc_no_secapi`, `strict_13_fast_no_qc_secapi`, `strict_12_fast_no_qc_no_secapi`.

## P7–P11 — card pipeline (EP)

- **P7 logo**: hard rule — create the per-run `cards/` directory **first**, save `logo_official.png` into it, set `logo_asset_path` to that absolute path, only then proceed. Order matters; see `MEMORY.md`.
- **P8 content**: produces `cards/{stem}.card_slots.json` with all 17 top-level keys.
- **P8.5 hardcode audit**: every sentence has a company-specific anchor; no boilerplate.
- **P9 layout**: compress to char/pixel budgets — do not invent facts.
- **P10 Validator 1**: `python tools/photo/validate_cards.py`. Exit 0 required.
- **P10.5 Validator 2**: web fact-check. Any change to `card_slots.json` → rerun P10. Loop cap 3.
- **P11 render**: 6 PNGs at 2160×2700, palette = `P0_palette`.

## P12 — paying-customer audit ★

Four layers in order, via `agents/post_card_auditor.md`:

| Layer | Tool | Fail blocks? |
|---|---|---|
| 1. Numerical reconciliation | `tools/audit/reconcile_numbers.py` | yes |
| 2. OCR over the 6 PNGs | `tools/audit/ocr_cards.py` | yes |
| 3. Web third-check (top-3 numbers) | `tools/audit/web_third_check.py` | yes |
| 4. DB cross-validate | `tools/audit/db_cross_validate.py` | no (cold-start OK) |

Output: `validation/post_card_audit.json` + human-readable `validation/QA_REPORT.md`. Never skip P12 unless the user types "skip audit / 跳过审计" in the same turn — and even then, log a `phase_skipped` event.

## P_DB_INDEX — persistence

Runs **only** after P12 reports `status: pass` (or warn-only). `python tools/db/index_run.py --run-dir <run_dir>` — single transaction, rollback on failure. Append-only `intelligence_signals` and `disclosure_quirks` survive partial-run admission with an analyst note.

## Failure caps (from MEMORY.md)

| Loop | Cap |
|---|---|
| ER subagent retry (same prompt) | 2 |
| `P10.5_validator2` ↔ `P10_validator1` | 3 |
| `P5.5` → `P5` (data validation fail → rewrite) | 2 |
| Subagent timeout retry | 1 (×1.5 multiplier); second timeout = phase failure |
| `P12` auto-retry | 0 (surface to user with run-dir path) |

## Resume semantics

If `meta/run.jsonl` already exists at start, you are in a resume context. Find the last `phase_exit` event; restart from the next phase. Inputs that already exist on disk and are schema-valid are reused — do not re-call subagents whose outputs are already present.
