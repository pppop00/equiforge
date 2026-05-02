# equiforge

A portable AI skill pack that fuses two existing skills — **Equity Research** (multi-agent → interactive HTML research report) and **Equity Photo** (HTML → 6 fixed-layout PNG social cards) — into a single end-to-end workflow with a persistent SQLite knowledge base and a four-layer post-card audit.

**One prompt → full delivery.** Type "研究一下苹果" (or "research Apple"); the harness runs language gate → SEC email gate → palette gate → research pipeline → card pipeline → final audit, and lands a per-run output folder with research JSON, the HTML report, the 6 PNG cards, the QA report, and a snapshot of the rows written to the local database.

## What's distinctive

- **Portable** — markdown agents + Python tools. Runs in Claude Code, Cursor, or any host that can read markdown briefs and execute Python. No runtime lock-in.
- **Audited** — every run produces a `meta/run.jsonl` event log, frozen system prompt, submodule SHAs, and a four-layer P12 audit (numerical reconciliation + PNG OCR + web third-check + DB cross-validation).
- **Cumulative** — every successful run writes financials, macro factors, Porter scores, prediction waterfalls, intelligence signals, and disclosure quirks into `db/equity_kb.sqlite` (SQLite + FTS5). Next quarter's Apple run reuses last quarter's Apple data; Apple's run can be cross-checked against Samsung if Samsung is in the DB.

## Repository layout

equiforge is a **harness-backed skill**: delivered as a skill (`SKILL.md` is the auto-trigger entry), maintained as a production harness (`HARNESS.md` is the architecture doc). The split is deliberate — see `HARNESS.md` for why.

```
equiforge/
├── SKILL.md                 # ★ thin skill entry — boot order, P0 gates, pointers
├── HARNESS.md               # harness/architecture/CLI/tests — start here for maintenance
├── MEMORY.md                # project invariants (frozen at session start)
├── USER.md                  # per-user preferences (gitignored; copy from .template)
├── workflow_meta.json       # machine-readable phase/gate contract
├── equiforge.py             # CLI entry (init, status)
│
├── agents/                  # equiforge-owned briefs only (orchestrator, gates, auditors)
│                            # upstream ER/EP agents stay under skills_repo/ — see HARNESS.md
├── references/              # lazy-loaded skill docs
│   ├── phase_contract.md
│   ├── p0_gates.md
│   ├── subagent_toolsets.md
│   ├── run_artifacts.md
│   ├── cross_quarter.md
│   └── maintenance.md
├── skills/                  # procedural how-tos (markdown)
├── tools/                   # Python CLIs (research/, photo/, audit/, db/, web/, io/)
├── skills_repo/             # git submodules
│   ├── er/   → Equity Research Skill
│   └── ep/   → Equity Photo Skill
├── db/
│   ├── equity_kb.sqlite     # gitignored; built from db/schema/*.sql
│   ├── schema/              # numbered SQL migrations
│   └── sector_reports/      # gitignored; cross-company reports rebuilt on demand
├── tests/                   # pytest suite
└── output/                  # gitignored; one folder per run (see references/run_artifacts.md)
```

## Quick start

```bash
git clone <this-repo-url> equiforge
cd equiforge
git submodule update --init --recursive    # pull ER + EP submodules
pip install -r requirements.txt
python equiforge.py init                   # build db/equity_kb.sqlite
cp USER.md.template USER.md                # then edit defaults

# Open the project in Claude Code / Cursor / etc., point the assistant at SKILL.md,
# then type:  研究一下苹果   (or)   research Apple
```

## How it works

12 phases, three of which block on user input (language, SEC email if US-listed, palette). Everything else is autonomous.

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
  → P5 HTML report writer (locked SHA256-pinned template — no simplified bypass)
  → P5_gate tools/research/validate_report_html.py (line/section/JS/marker hard gate)
  → P5.5 final data validator (CFA-level)
  → P6 report validator + packaging profile (one of four whitelisted)
  → P7 logo production (≥840px wide; saved to output dir first)
  → P8 card content production
  → P8.5 hardcode/logic audit
  → P9 layout fill (char/pixel budgets)
  → P10 Validator 1 (scripts/validate_cards.py)
  → P10.5 Validator 2 (web fact-check; loops back to P10 ≤3×)
  → P11 render 6 PNGs (2160×2700)
  → P12 final audit: reconcile + OCR + web third + DB cross  ★ paying-customer gate
  → P_DB_INDEX writes everything into db/equity_kb.sqlite
```

See `workflow_meta.json` for the machine-readable contract, `agents/orchestrator.md` for the runtime brief, `references/phase_contract.md` for the prose phase narrative, and `HARNESS.md` for the harness architecture.

## Cross-quarter and cross-company reuse

After a few runs, the database lets you:

- **Skip macro re-collection** — if a run for *any* US-listed company in 2026Q2 has already collected the 6-factor US macro vector, the next 14 days of US runs short-circuit `macro_scanner` and pull from DB.
- **Cross-validate against history** — running Apple in Q3 will compare the new financials against Apple's Q1/Q2 rows already in DB; YoY > 5pp delta from reported flags as CRITICAL.
- **Cross-validate against peers** — Apple's Porter `rivalry=3` while Samsung (DB) is `5`: P12 flags as a peer-divergence warning for analyst review.
- **Generate sector reports** — `python tools/db/sector_report.py --type porter_heatmap --sector "Information Technology" --period 2026Q2` produces a force × peer matrix HTML+JSON.

## Locked report template

Every run delivers two artifacts: **one HTML report and six PNG cards.** The HTML report is always produced by filling the SHA256-pinned locked skeleton extracted via `tools/research/extract_template.py` — there is **no institution-compatible / private-company / scope-limited / simplified bypass**.

- Public issuers, private funds, hedge funds, family offices, government entities — same locked template, every time.
- When issuer-level financials are unavailable, the report writer fills the locked sections with the best available proxies (AUM, strategy, top holdings, manager-level filings, peer macro) and labels residual gaps inline. It does not drop sections, shorten the template, or hand-write a summary page.
- After P5, `tools/research/validate_report_html.py` is a hard gate (line count ≥ 500, six section IDs, locked CSS/JS markers, chart data variables, no `{{PLACEHOLDER}}` remaining). Non-zero exit ⇒ discard the HTML and rerun P5 from the extracted skeleton.
- `report_validation.txt`'s top-line status is one of `pass | warn | critical` — fabricated values like `pass_with_scope_limitations` or `not_applicable` are P6 violations.
- `structure_conformance.json -> profile` must be one of the four whitelisted in `workflow_meta.json -> packaging_profiles`. The picker is `(qc_mode, sec_api_mode)`; new profile names are not allowed.

## Privacy

- SEC EDGAR User-Agent emails are never persisted. They live for the duration of one HTTP request only.
- `tests/test_db_pii.py` asserts that no row in any TEXT column matches an email regex after a known-input fixture run.

## Status

The machine-readable orchestration contract is `workflow_meta.json` (phases, tools, agents, gates). Upstream skills (`skills_repo/er`, `skills_repo/ep`) are pinned by SHA via `.gitmodules`; submodule bumps are deliberate and logged in `meta/submodule_shas.json` per run.

## License

Apache-2.0, matching both upstream skills.
