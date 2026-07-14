---
schema_version: 1
date: 2026-07-13
status: implemented
description: Decision record for replacing the four-card investment/CFA pack with the five-card company-country knowledge map.
---

# Five-card knowledge-map migration (schema v5)

## Decision

Anamnesis Research now has one product task:

> Through one listed company, help the reader understand how it makes money, which variables determine results, where the main risks arise, and how national institutions and culture shape the company.

New runs produce five continuous cards:

1. `01_cover.png` — one-minute company understanding
2. `02_porter.png` — industry forces and external variables
3. `03_five_year_financials.png` — how the business model becomes financial results
4. `04_company_quality.png` — valuation, governance, capital allocation, and accounting quality
5. `05_country_lens.png` — understanding a country through the company

The locked HTML report remains the evidence and audit base. Its page skeleton was not changed.

## Why this changed

The previous pack mixed three possible products: investment research, CFA teaching, and a company-based country knowledge map. CFA Lens was useful for finance education but did not directly improve the intended one-minute reader outcome. Standardized cards also risked implying that differently defined FCF, ROE, Capex, net debt, fiscal periods, currencies, geographic revenue, and valuation multiples were automatically comparable.

The v5 design therefore makes four changes:

- centers the pack on business model, result variables, primary risk, and country context;
- replaces CFA Lens with company quality and a balanced Country Lens;
- makes metric basis and claim provenance machine-readable rather than adding visible confidence badges;
- distinguishes company disclosure, external fact, analyst calculation, external estimate, inference, and forecast through natural-language attribution plus a complete evidence sidecar.

## Research and metadata changes

- P1 adds `company_context_researcher`; four research jobs retain concurrency cap 3.
- P2 adds `company_quality.json`, `country_lens.json`, and `metric_basis.json`.
- P3.7 runs a blocking Metric Basis validator over FCF, ROE, Capex, net debt, fiscal year, currency/unit, geographic revenue, and valuation.
- `card_slots_worker_notes.json` now stores claim-level evidence: `claim_id`, `slot_path`, `epistemic_type`, `source_refs`, `as_of_date`, optional `basis_id`, and optional `falsifier`.
- Missing information remains visible as `未披露` or `不可比` with a reason; no composite company-quality score is generated.

## Card and layout changes

- Card 1 uses `one_minute_summary`; its two variables are rendered as separate centered lines. Labels and bodies are centered inside measured row cells rather than positioned by baseline guesses.
- Card 2 retains Porter but requires an ordered chain: external condition → transmission → company outcome → watch signal. The former section heading was removed to give each step a larger measured row and prevent overlap.
- Card 3 connects the five-year business shift to revenue, profit, and cash flow. Its quantitative panel participates in P12 reconciliation and OCR.
- Card 4 is a 2×2 company-quality panel without a synthetic score.
- Card 5 separates incorporation, listing, operations, and revenue exposure, then applies six country dimensions as country fact → company transmission → observable metric.

## Harness, audit, and persistence changes

- P8–P12, both validators, both red teams, render wrappers, delivery paths, OCR routing, reconciliation, and web third-check use the five-card contract.
- P12 now maps Card 2 correctly and audits Card 3 financial metrics, Card 4 valuation, and Card 5 quantitative country claims.
- SQLite migration `003_knowledge_map_v5.sql` adds `claim_evidence`, `metric_basis_period`, `company_quality_observations`, and `country_lens_observations`.
- New Card 4 and Card 5 paths use the existing `card4_png_path` and `card5_png_path`. Historical CFA columns and rows remain unchanged.
- All new TEXT/JSON persistence paths retain recursive email PII scrubbing.

## Compatibility and migration rules

- New rendering requires schema v5. Schema v3/v4 slots are rejected and must rerun P8.
- Historical four-card artifacts are not rewritten or deleted.
- `cfa_lens`, the CFA selector, `--cfa-progress`, CFA voice rules, and `04_cfa_lens.png` are absent from the active path.
- Historical CFA validators and database columns remain only for archived-run compatibility. Incident I-012's formula-substitution check is explicitly gated to schema versions below 5.
- No sibling-working-copy fallback was added; runtime resolution remains SHA-pinned to `skills_repo/er` and `skills_repo/ep`.

## Related incident hardening in this revision

This revision also preserves two already-confirmed failure records that were present in the worktree:

- I-011: locked-report appendix rows must populate all four cells, including controlled confidence text.
- I-012: archived CFA formulas that divide by market value must include numerator, denominator, and computed result. This is historical compatibility logic and is not used by schema v5.

## Pinned upstream revisions

- EP: `1be0d80476abd6f4b9ec9810582473ea31bef635` on `codex/five-card-knowledge-map-v5`
- ER: `b08d8a77419dff489d7260202ef0c40869715a52` on `codex/company-country-context-v5`

## Validation performed

- Anamnesis: 170 passed, 2 skipped
- EP: 43 passed
- ER: 37 passed
- Root and ER workflow validators: pass
- skill-creator `quick_validate.py`: pass for Anamnesis, EP, and ER
- Fast Retailing full render: five PNGs at 2160×2700, visually inspected
- OCR: all five cards pass
- Numerical reconciliation: 33/33 pass
- Metric Basis validation and independent official-source third check: pass
- Temporary clean-database index: 13 claims, 9 metric bases, 4 company-quality observations, 6 country-lens observations, and zero email PII hits

## Deliberately deferred

- Visible confidence badges, user-facing version history, prediction scorecards, and change logs per card are not added.
- The existing data date remains the visible date.
- The non-blocking human reader study still requires at least five real readers, an immediate test after 60 seconds, and a seven-day unaided retest. Agents must not simulate it; see `references/reader_test.md`.
