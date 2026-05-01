# equiforge — harness architecture

equiforge is delivered as a skill (entry: `SKILL.md`) and maintained as a production harness (this file). The skill side tells the model *what to do*; the harness side defines *how the run is executed, persisted, audited, and resumed*. If you are running the pipeline, read `SKILL.md`. If you are extending the harness — adding a tool, changing the DB schema, wiring a new audit layer — start here.

## Two contracts, one repo

| Surface | Audience | Source of truth |
|---|---|---|
| Skill (auto-triggered) | LLM / Codex / Claude | `SKILL.md` (frontmatter + boot order) |
| Workflow contract | Both | `workflow_meta.json` (machine-readable phases) |
| Project invariants | LLM | `MEMORY.md` (frozen at session start) |
| User preferences | LLM | `USER.md` (gitignored, sticky) |
| Runtime brief | Orchestrator subagent | `agents/orchestrator.md` |
| Reference docs | Lazy-loaded by the model | `references/*.md` |
| Maintainer architecture | Humans (you, future you) | `HARNESS.md` (this file) |

The split exists because the skill anatomy spec only allows `name` + `description` in frontmatter, and SKILL bodies should stay under ~500 lines for progressive disclosure. Anything heavier (phase contract, subagent toolset whitelist, run-dir layout, maintenance notes) lives in `references/` and is read on demand.

## Repository layout

```
equiforge/
├── SKILL.md                # ★ skill entry — thin, strict, auto-triggered
├── HARNESS.md              # this file — harness/architecture/CLI/tests
├── MEMORY.md               # project invariants, frozen at session start
├── USER.md.template        # copy → USER.md (gitignored), sticky preferences
├── workflow_meta.json      # machine-readable phase + gate contract
├── equiforge.py            # CLI entry (init, status, etc.)
│
├── agents/                 # equiforge-owned briefs ONLY (no symlinks to upstream)
│   ├── orchestrator.md
│   ├── intent_resolver.md
│   ├── language_gate.md / sec_email_gate.md / palette_gate.md
│   ├── post_card_auditor.md
│   └── cross_validator.md
│   # ER/EP subagents live at skills_repo/{er,ep}/agents/*.md and are referenced
│   # by their real paths in workflow_meta.json — never aliased into agents/.
│
├── references/             # lazy-loaded skill docs
│   ├── phase_contract.md
│   ├── p0_gates.md
│   ├── subagent_toolsets.md
│   ├── run_artifacts.md
│   ├── cross_quarter.md
│   └── maintenance.md
│
├── tools/                  # Python CLIs (one tool per concern)
│   ├── research/   ├── photo/   ├── audit/
│   └── db/         ├── web/     └── io/
│
├── skills_repo/            # git submodules (pinned by SHA)
│   ├── er/                 # Equity Research Skill (P1..P6)
│   └── ep/                 # Equity Photo Skill (P7..P11)
│
├── db/
│   ├── equity_kb.sqlite    # gitignored runtime
│   ├── schema/00X_*.sql    # numbered, additive migrations
│   ├── seed/               # optional fixture data
│   └── sector_reports/     # gitignored, regenerated on demand
│
├── tests/                  # pytest suite (CLI, migrations, PII, reconcile, etc.)
└── output/                 # gitignored runtime — one folder per run
    └── {Company}_{Date}_{RunID}/   # see references/run_artifacts.md
```

## CLI

```bash
# First-time setup
git clone <repo> equiforge
cd equiforge
git submodule update --init --recursive
pip install -r requirements.txt
python equiforge.py init                # builds db/equity_kb.sqlite from db/schema/
cp USER.md.template USER.md             # then edit defaults

# Pre-flight
pytest -q                               # must be green before any production run
python tools/research/validate_workflow_meta.py

# Bootstrap a run dir (the orchestrator does this; CLI for debugging)
python tools/io/run_dir.py --company apple --date 2026-04-30 --run-id $(python -c 'import secrets;print(secrets.token_hex(4))')

# Index a finished run (P_DB_INDEX; orchestrator runs this after P12 passes)
python tools/db/index_run.py --run-dir output/Apple_2026-04-30_<RunID>/

# Sector reports (regenerate on demand)
python tools/db/sector_report.py --type porter_heatmap --sector "Information Technology" --period 2026Q2
```

## Run state

Every run has a stable directory under `output/{Company}_{Date}_{RunID}/`. The full subfolder layout is in `references/run_artifacts.md`. Two files are load-bearing for resume:

- `meta/run.jsonl` — append-only event log. `phase_enter` / `phase_exit` / `phase_failed` / `phase_skipped`.
- `meta/system_prompt.frozen.txt` — the resolved `MEMORY.md` + `USER.md` snapshot. Frozen at session start so audits can replay.

If `meta/run.jsonl` exists at start, the orchestrator is in resume context: it walks the log to the last `phase_exit` and restarts from the next phase. Schema-valid outputs already on disk are reused — no double-billing the LLM.

## Database

SQLite single-file at `db/equity_kb.sqlite`. Schema is migration-driven:

- Each change is a new `db/schema/00X_*.sql` with a `PRAGMA user_version` bump.
- Additive only — never drop a column or table. Rename via `ADD COLUMN` + dual-write window.
- `tests/test_db_migrations.py` verifies migrations apply cleanly to both cold and existing DBs.
- `tests/test_db_pii.py` regression-tests that no TEXT column persists an email after a fixture run (SEC EDGAR User-Agent leak guard).

Cross-quarter / cross-company reuse details are in `references/cross_quarter.md`.

## Audit

The four-layer P12 audit (numerical reconciliation, PNG OCR, web third-check, DB cross-validate) is the paying-customer gate. The orchestrator must not write to the DB if P12 fails.

- Numerical tolerances live in two places that must stay in sync: `MEMORY.md` (contract) and `tools/audit/reconcile_numbers.py` (enforcer). See `references/maintenance.md`.
- Web third-check uses an independent search path from Validator 2 — they must not share a session.
- DB cross-validate is fail-soft on cold start (`cold_start_ok: true` in `workflow_meta.json`).

## Tests

```bash
pytest -q                                 # full suite
pytest tests/test_db_pii.py -v            # PII regression
pytest tests/test_aggregate_p12.py -v     # P12 layer aggregation
pytest tests/test_reconcile_numbers.py -v # tolerance enforcement
pytest tests/test_db_migrations.py -v     # cold + existing DB
pytest tests/test_queries_cold_start.py   # DB precheck cold-start contract
```

`tests/conftest.py` sets up an in-memory SQLite for migration tests and a fixture run-dir for aggregation tests.

## Submodule policy

`skills_repo/er` and `skills_repo/ep` are pinned by SHA in `.gitmodules`. Bumps are deliberate, not automatic. Each run records the resolved SHAs to `meta/submodule_shas.json`. To bump:

```bash
cd skills_repo/er && git fetch && git checkout <sha> && cd ../..
git add skills_repo/er
pytest -q                                  # must be green
git commit -m "bump er submodule to <short-sha>"
```

If the upstream ER skill changes the locked HTML template, the upstream maintainer updates the SHA256 in `skills_repo/er/tests/test_extract_report_template.py`. Equiforge picks it up on the next bump.

### Why root `agents/` is equiforge-only (no symlinks to upstream)

`agents/` contains **only** equiforge's own orchestration briefs (`orchestrator`, `intent_resolver`, the four gate agents, `cross_validator`, `post_card_auditor`). It does **not** symlink or alias the upstream `skills_repo/er/agents/*` and `skills_repo/ep/agents/*` files. Why:

- **One canonical path per agent.** `meta/run.jsonl` and audit artifacts always log the real path. No "did this come from the symlink or the submodule?" ambiguity.
- **Stale-symlink risk on submodule bumps.** Renames upstream silently break aliases while `ls agents/` still looks healthy. Since nothing reads the aliases, the breakage stays invisible until a live phase fails.
- **Semantic separation.** `agents/` is for things equiforge owns and can change. `skills_repo/{er,ep}/agents/` is upstream territory we pin and consume.
- **Future-proof for `agents/openai.yaml`.** When we add UI/runtime metadata at `agents/openai.yaml`, the directory should not also contain dozens of upstream-owned briefs — the two concerns don't belong together.

`workflow_meta.json` and `agents/orchestrator.md` reference upstream agents by their **real submodule path** (`skills_repo/er/agents/financial_data_collector.md`, `skills_repo/ep/agents/logo-production-agent.md`, etc.). The path is the audit surface — keep it honest.

Symlinking back into `agents/` would only be justified if some harness or environment could only read from a single flat directory. Equiforge has no such constraint, so we don't pay the cost.

## What this harness deliberately does not do

- **No skill self-improvement / DSPy / GEPA optimizer.** Auditability beats agility. Every numeric in a card is traceable to a source JSON to a frozen system prompt to a submodule SHA.
- **No code-execution sandbox.** Everything is a registered tool under `tools/`. The LLM cannot exec arbitrary Python.
- **No multi-tenant routing.** Single user, local SQLite, single process. Run two equiforges in two terminals if you want concurrency.
- **No streaming UI.** CLI in, files out. The output folder is the deliverable.

## When to update what

| You are changing… | Update |
|---|---|
| What the skill triggers on | `SKILL.md` description |
| Boot order / commands the model must run | `SKILL.md` body |
| What a phase produces / its tool | `workflow_meta.json` + `references/phase_contract.md` |
| Per-gate rules (whitelist, sticky source) | `references/p0_gates.md` |
| Subagent toolset scope | `references/subagent_toolsets.md` |
| Numerical tolerances | `MEMORY.md` AND `tools/audit/reconcile_numbers.py` (both, every time) |
| DB schema | new `db/schema/00X_*.sql` + bump `PRAGMA user_version` + run migration tests |
| Locked HTML template | upstream `skills_repo/er` only — equiforge bumps the submodule |
| Architecture / CLI / dev workflow | this file (`HARNESS.md`) |
