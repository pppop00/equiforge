#!/usr/bin/env python3
"""UserPromptSubmit hook for equiforge.

Fires on every prompt submission. If the prompt looks like an equity-research
request (matches a small whitelist of trigger phrases in EN/ZH), inject a hard
reminder that points the model at INCIDENTS.md and MEMORY.md before any phase
work. Otherwise no-op.

Hook protocol: read JSON event from stdin; if we want to inject context,
write JSON to stdout with `additionalContext`; exit 0. Exit non-zero only on
hook errors (not to block the user).

Why this exists: even when SKILL.md auto-triggers, the model can drift mid-run
and skip a P0 gate or the locked template. INCIDENTS.md is the cheapest
intervention — re-injecting its rules at every research-style prompt makes
relapse expensive.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

TRIGGER_PATTERNS = [
    r"\bresearch\b",
    r"\bwriteup\b",
    r"\bone[- ]?pager\b",
    r"\bequity\s+research\b",
    r"\bcards?\s+for\b",
    r"\banalyst.{0,10}note\b",
    r"研究",
    r"分析",
    r"研报",
    r"做.{0,4}研究",
    r"看看.{0,8}(公司|股票|苹果|腾讯|阿里|美股|港股)",
    r"build\s+cards",
]

TRIGGER_RE = re.compile("|".join(TRIGGER_PATTERNS), re.IGNORECASE)


def looks_like_research(prompt: str) -> bool:
    return bool(TRIGGER_RE.search(prompt or ""))


def build_context() -> str:
    incidents = REPO_ROOT / "INCIDENTS.md"
    memory = REPO_ROOT / "MEMORY.md"
    skill = REPO_ROOT / "SKILL.md"

    lines = [
        "[Anamnesis Research harness reminder — injected by .claude/hooks/inject_incidents.py]",
        "",
        "This prompt looks like an equity-research request. This project is Anamnesis Research (codename: equiforge), an implementation of the Anamnesis Pattern. Before any phase work:",
        f"1. Read {skill.relative_to(REPO_ROOT)} for the boot order and P0 gates.",
        f"2. Read {memory.relative_to(REPO_ROOT)} for project invariants (frozen at session start).",
        f"3. Read {incidents.relative_to(REPO_ROOT)} end-to-end. Acknowledge each incident in meta/run.jsonl as `incident_precheck.acknowledged` during P_INCIDENT_PRECHECK.",
        "",
        "Hard reminders (the two recurring failure modes):",
        "- Interactive P0 gates (P0_lang / P0_sec_email / P0_palette) cannot be auto-defaulted. Auto mode does not waive them. Halt and ask if no user_response and no USER.md sticky exists. (See INCIDENTS I-001.)",
        "- The locked HTML template applies to EVERY company — public, private, fund, family office, government. There is no scope-limited / institution-compatible / simplified bypass. Fill the locked skeleton with proxies and label gaps; never hand-write a simplified report. (See INCIDENTS I-002.)",
    ]
    return "\n".join(lines)


def main() -> int:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        # Don't block the user on a malformed event — just no-op.
        return 0

    prompt = event.get("prompt") or event.get("user_prompt") or ""

    if not looks_like_research(prompt):
        return 0

    output = {"additionalContext": build_context()}
    sys.stdout.write(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
