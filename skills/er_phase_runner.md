---
schema_version: 1
name: er_phase_runner
description: How to walk ER phases P1..P6 in this fused orchestrator. Wraps skills_repo/er/SKILL.md but adds DB short-circuits and per-run output dir.
when_to_use: After P0 gates pass, drive the research half of the pipeline.
requires_toolsets: ["research", "web", "io", "db"]
---

# /er_phase_runner

| Phase | Action | Run-dir output |
|---|---|---|
| P0_DB_PRECHECK | `tools/db/queries.py` calls — populate prior_financials, peer_companies, macro_snapshot | `db_export/peer_context.json`, `db_export/prior_financials_used.json` |
| P1 (parallel ×3) | Delegate `financial_data_collector.md` + `macro_scanner.md` + `news_researcher.md` (concurrency cap 3). Pass DB precheck results into each — esp. `macro_scanner` short-circuits if a fresh snapshot exists. | `research/financial_data.json`, `research/macro_factors.json`, `research/news_intel.json` |
| P1.5 | Sequential. Delegate `edge_insight_writer.md` with all P1 outputs. | `research/edge_insights.json` |
| P2 | Inline (or fresh subagent). Compute `financial_analysis.json` from P1 + P1.5. | `research/financial_analysis.json` |
| P2.5 | Inline. Build `prediction_waterfall.json`: baseline + macro adjustments + company_events_detail bridge. | `research/prediction_waterfall.json` |
| P2.6 (parallel ×2) | `qc_macro_peer_a.md` + `qc_macro_peer_b.md`. Same inputs, different lenses. Both must complete. | `research/qc_macro_peer_{a,b}.json` |
| P3 | Inline. Build `porter_analysis.json` — three perspectives × five forces, threat scale 1-5. | `research/porter_analysis.json` |
| P3.5 (parallel ×2) | `qc_porter_peer_a.md` (Buffett moat) + `qc_porter_peer_b.md` (Munger structural). Both must complete. | `research/qc_porter_peer_{a,b}.json` |
| P3.6 | `qc_resolution_merge.md`. Apply weighted scoring 0.34/0.33/0.33; only change scores when delta>1.0. Write `qc_audit_trail.json` and update `prediction_waterfall.json` + `porter_analysis.json` in place with `qc_deliberation`. | `research/qc_audit_trail.json` |
| P3.7 | `agents/cross_validator.md` (this project). Six checks against DB. CRITICAL findings block. | `research/cross_validation.json` |
| P4 | Inline. Inject Sankey payload into `financial_analysis.json` based on income statement totals. | (modifies `research/financial_analysis.json`) |
| P5 | `tools/research/extract_template.py --lang <cn\|en>` → skeleton. Then `report_writer_{cn,en}.md` substitutes `{{PLACEHOLDER}}` markers. | `research/_locked_skeleton.html`, `research/{Company}_Research_{LANG}.html` |
| P5.5 | `final_report_data_validator.md` — CFA-grade audit. CRITICAL → loop back to P5 (cap 2). | `research/final_report_data_validation.json` |
| P6 | `tools/research/packaging_check.py` → `report_validator.md` — choose packaging profile. | `research/report_validation.txt`, `research/structure_conformance.json` |

## DB short-circuits the orchestrator hands to ER agents

When delegating to P1 subagents, append to each task prompt:

- `financial_data_collector`: `Prior periods already in DB: <list of period_ids from prior_financials_used.json>. Skip those; collect only new period(s).`
- `macro_scanner`: `Fresh macro snapshot for <geography>, <period>: <inline JSON if present, else "none">. If present, REUSE it (do not re-collect); only validate freshness.`
- `news_researcher`: `Peer companies in DB: <list>. Reference them by ticker in cross-section narratives.`

## Where ER skill's instructions live

For the actual content rules (what each agent must extract / produce), read `skills_repo/er/SKILL.md` and the per-agent files under `skills_repo/er/agents/`. This skill only orchestrates.
