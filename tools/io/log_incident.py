#!/usr/bin/env python3
"""Backend for the /log-incident slash command.

The slash command spec lives at `.claude/commands/log-incident.md`. This tool
collects evidence — the latest run dir, a digest of run.jsonl, gates.json,
run.json, and any structural validation outputs — and prints it as JSON for
the model to read. The model uses that evidence to draft a candidate
INCIDENTS.md entry, which it shows the user for confirmation before appending.

This tool is read-only. It does NOT write to INCIDENTS.md — that is the
model's job under user supervision, via Edit.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "output"
INCIDENTS = REPO_ROOT / "INCIDENTS.md"

JSONL_TAIL = 50


def latest_run_dir() -> Path | None:
    if not OUTPUT_DIR.is_dir():
        return None
    candidates = [p for p in OUTPUT_DIR.iterdir() if p.is_dir() and (p / "meta").is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_jsonl_tail(path: Path, n: int = JSONL_TAIL) -> list[dict]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-n:]
    out: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            out.append({"_raw": line, "_parse_error": True})
    return out


def read_json(path: Path) -> object | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def collect(run_dir: Path | None) -> dict:
    target = run_dir or latest_run_dir()
    if target is None:
        return {
            "run_dir": None,
            "error": "no run dir found under output/",
            "today": datetime.now().strftime("%Y-%m-%d"),
            "next_incident_id": next_incident_id(),
        }

    meta = target / "meta"
    validation = target / "validation"
    research = target / "research"

    digest = {
        "run_dir": str(target),
        "today": datetime.now().strftime("%Y-%m-%d"),
        "next_incident_id": next_incident_id(),
        "run_json": read_json(meta / "run.json"),
        "gates_json": read_json(meta / "gates.json"),
        "submodule_shas": read_json(meta / "submodule_shas.json"),
        "run_jsonl_tail": read_jsonl_tail(meta / "run.jsonl"),
        "structure_conformance": read_json(research / "structure_conformance.json"),
        "report_validation_txt": (
            (research / "report_validation.txt").read_text(encoding="utf-8")
            if (research / "report_validation.txt").is_file()
            else None
        ),
        "post_card_audit": read_json(validation / "post_card_audit.json"),
        "incident_postcheck": read_json(validation / "incident_postcheck.json"),
        "red_team_numeric_p5_7": read_json(validation / "red_team_numeric_P5_7_RED_TEAM.json"),
        "red_team_narrative_p5_7": read_json(validation / "red_team_narrative_P5_7_RED_TEAM.json"),
        "red_team_numeric_p10_7": read_json(validation / "red_team_numeric_P10_7_RED_TEAM.json"),
        "red_team_narrative_p10_7": read_json(validation / "red_team_narrative_P10_7_RED_TEAM.json"),
    }
    return digest


def next_incident_id() -> str:
    if not INCIDENTS.is_file():
        return "I-001"
    text = INCIDENTS.read_text(encoding="utf-8")
    ids: list[int] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## I-"):
            try:
                num = int(line.split("##")[1].strip().split()[0].split("-")[1])
                ids.append(num)
            except (IndexError, ValueError):
                continue
    nxt = (max(ids) + 1) if ids else 1
    return f"I-{nxt:03d}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect", action="store_true", help="collect digest of latest run for incident drafting")
    parser.add_argument("--run-dir", type=Path, default=None, help="override the auto-detected latest run dir")
    args = parser.parse_args()

    if not args.collect:
        parser.print_help()
        return 2

    digest = collect(args.run_dir)
    json.dump(digest, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
