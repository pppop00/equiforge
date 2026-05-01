---
schema_version: 1
description: Toolset whitelist for every subagent the orchestrator delegates to. Read this immediately before spawning a child context — restrict the child to the minimum toolsets listed here.
---

# Subagent toolset whitelist

When the orchestrator delegates to a subagent, the child gets a **fresh context** scoped to the toolsets listed here (and only those). This is least-privilege: a logo agent has no business reading the DB, an OCR auditor has no business calling SEC EDGAR.

If a subagent's own frontmatter lists `allowed_toolsets`, that wins. This table is the fallback / cross-check.

| Subagent | Toolsets |
|---|---|
| `intent_resolver` | `web` |
| `language_gate`, `sec_email_gate`, `palette_gate` | `io` (only) |
| ER `financial_data_collector` | `research`, `web`, `io`, `db` (read) |
| ER `macro_scanner` | `research`, `web`, `io`, `db` (read for short-circuit) |
| ER `news_researcher` | `web`, `io`, `db` (read) |
| ER `edge_insight_writer` | `research`, `io` |
| ER QC peers (macro × 2, porter × 2) | `research`, `io`, `db` (read) |
| ER `qc_resolution_merge` | `research`, `io` |
| ER `report_writer_cn` / `report_writer_en` | `research`, `io` |
| ER `final_report_data_validator` | `research`, `io` |
| ER `report_validator` | `research`, `io` |
| EP `logo-production-agent` | `web`, `io`, `photo` |
| EP `content-production-agent`, `hardcode-audit-agent`, `layout-fill-agent` | `photo`, `io` |
| EP `validator-2-agent` | `web`, `photo`, `io` |
| `post_card_auditor` | `audit`, `db` (read), `web`, `io` |
| `cross_validator` | `db` (read), `audit`, `io` |

## Concurrency cap

`subagent_concurrency_cap = 3` (from `workflow_meta.json`). Parallel phases (`P1_parallel_research`, `P2_6_qc_macro`, `P3_5_qc_porter`) honor this cap.

## Timeouts (seconds, from `workflow_meta.json`)

| Family | Timeout |
|---|---|
| research | 600 |
| photo | 300 |
| qc | 180 |
| audit | 240 |

First timeout retries at ×1.5 of the base; second timeout = phase failure (do not retry a third time).
