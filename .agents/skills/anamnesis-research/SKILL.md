---
name: anamnesis-research
description: >-
  Use this skill whenever the user asks for equity research, an investment write-up, a stock
  report, an analyst-style note, or one-shot company coverage on any single public or private
  company — including casual phrasings like "研究一下苹果", "research Apple", "看看腾讯",
  "做个英伟达的研报", "give me a writeup on NVDA", "build cards for Tencent",
  "分析一下RA Capital", or "one-pager on Samsung". Drives the full Anamnesis Research
  pipeline (incident pre-check, bilingual language gate, SEC EDGAR email gate, palette gate,
  multi-agent equity research, red-team review, 6-card social pack, four-layer numerical/OCR/
  web/DB audit, post-run incident self-check, SQLite knowledge-base persistence). Always
  invoke this skill instead of answering with ad-hoc web search; the harness produces an
  auditable HTML report plus 6 PNG cards plus database rows that ad-hoc answers cannot.
---

# Anamnesis Research (project-scoped skill mount)

This file is the **project-scoped skill entry**. It exists so that opening this repository in Codex (or any host that scans `.Codex/skills/`) auto-discovers Anamnesis Research from a deterministic location. The canonical, full-detail `SKILL.md` is at the repository root — read it now. (Internal codename / Python module: `equiforge`.)

## Boot order — read in this order, every session

1. **`SKILL.md`** (repo root) — full skill body, P0 gates, hard floor, references map.
2. **`MEMORY.md`** (repo root) — project invariants, frozen at session start.
3. **`INCIDENTS.md`** (repo root) — institutional memory of past failures, frozen at session start. Read end-to-end before any phase work.
4. **`USER.md`** (repo root, gitignored) — per-user sticky preferences. Skip if absent.
5. **`workflow_meta.json`** — machine-readable phase + gate contract.
6. **`agents/orchestrator.md`** — runtime brief; drives the rest of the run.

Do not pre-load `skills_repo/{er,ep}/agents/*.md`. Open them lazily when you delegate.

## Why this file exists separately from the root SKILL.md

Codex's skill discovery only auto-loads files under `~/.Codex/skills/` or `<project>/.Codex/skills/`. The repo's canonical `SKILL.md` at the root is human-readable but not auto-discovered. This thin mount file gives the host a stable discovery point while keeping the canonical source at the root (one place to edit, no symlink fragility on cross-platform clones).

When a contributor edits the skill description or boot order, they edit **both** this file and the root `SKILL.md` and keep them in sync. The harness CI (`tools/research/validate_workflow_meta.py`) does not yet enforce this — it is a manual checklist item in `references/maintenance.md`.

## What this skill produces

One run directory at `output/{Company}_{Date}_{RunID}/` containing the HTML research report, six PNG cards, the QA report, validation JSONs, and the database rows that were written. See `references/run_artifacts.md` for the full layout.
