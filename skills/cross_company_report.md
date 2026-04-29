---
schema_version: 1
name: cross_company_report
description: Generate sector- or peer-level analytical reports on demand from the local DB. Independent of the per-company run pipeline.
when_to_use: User asks for a peer comparison, sector heatmap, or aggregate macro consistency view across companies already in db/equity_kb.sqlite.
requires_toolsets: ["db", "io"]
---

# /cross_company_report

A standalone command that reads `db/equity_kb.sqlite` and produces sector-level analytical artifacts. Does **not** kick off a research pipeline.

## Available report types

```bash
python tools/db/sector_report.py --type <one_of> [--sector <sector>] [--period <period>] [--out <dir>]
```

| `--type` | What it produces |
|---|---|
| `porter_heatmap` | Force × peer 5×N grid (1-5 colour-coded) for `(sector, period)`; QC-flag overlay where the score changed in QC (from `qc_events.score_changed`). |
| `macro_consistency` | One row per `(geography, period)` showing 6-factor vector across last 8 quarters; QoQ drift highlighted; per-company variance overlay. |
| `peer_growth_attribution` | Side-by-side waterfall: baseline → macro adj → company-specific → predicted, for every peer in `(sector, period)`; identical x-axis. |
| `signal_taxonomy` | Histogram of `signal_type` × ticker for sector; FTS top-K facts per type. |

## Output

Each report writes to `db/sector_reports/{report_type}_{sector_slug}_{period}/`:
- `{report_type}.html` — interactive HTML (re-uses a stripped skeleton from ER's report templates)
- `{report_type}.json` — raw rows for re-ingestion as evidence in subsequent runs

## Cold-start

If the requested `(sector, period)` has fewer than 2 companies in DB, the script writes a minimal HTML noting "insufficient data" and exits 0 (not an error — just empty).

## Re-ingestion

The JSON output of these reports can be loaded by a subsequent run as evidence — e.g. when running Apple Q3 after running 5 other tech companies in Q3, the `porter_heatmap` JSON already in `db/sector_reports/` can be passed to `agents/cross_validator.md` to enrich peer divergence checks without re-querying.
