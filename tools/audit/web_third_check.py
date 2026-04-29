"""P12 layer 3 — independent web fact-check of the Top-N highest-impact numbers.

This is defense-in-depth above EP's Validator 2. After all the slot edits in V2's
loop, re-verify a small sample of headline numbers against authoritative sources
(IR, exchange filings, Bloomberg/Reuters).

The actual web search is delegated to the host's WebSearch / WebFetch — this script
just picks the Top-N targets and writes the audit envelope. Subagent
agents/post_card_auditor.md fills in `verified` / `disputed` per item.

Usage:
    python tools/audit/web_third_check.py --run-dir <path> --top-n 3
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _numerics import extract_numerics  # noqa: E402

# Headline metric keys we want to re-verify in priority order
PRIORITY_PATHS = [
    "card_slots.intro_sentence",
    "card_slots.company_focus_paragraph",
    "card_slots.judgement_paragraph",
    "card_slots.industry_paragraph",
    "card_slots.revenue_explainer_points",
]


def collect_priority_targets(slots: dict, top_n: int) -> list[dict]:
    targets: list[dict] = []
    seen_values: set[float] = set()
    for path in PRIORITY_PATHS:
        keys = path.split(".")
        node = slots
        for k in keys[1:]:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                node = None
                break
        if node is None:
            continue
        text_chunks = node if isinstance(node, list) else [node]
        for chunk in text_chunks:
            if not isinstance(chunk, str):
                continue
            for tok in extract_numerics(chunk, path=path):
                if tok.value in seen_values:
                    continue
                if tok.unit not in {"pct", "pp", "yi", "wan", "wanyi", "billion", "million", "x"}:
                    # skip dates and ordinals
                    continue
                seen_values.add(tok.value)
                targets.append({
                    "value": tok.value,
                    "raw": tok.raw,
                    "unit": tok.unit,
                    "context": tok.context,
                    "slot_path": tok.path,
                    "verification": "pending",
                    "source_url": None,
                    "source_value": None,
                    "notes": None,
                })
                if len(targets) >= top_n:
                    return targets
    return targets


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--top-n", type=int, default=3)
    p.add_argument("--ticker", default=None)
    p.add_argument("--period", default=None)
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    cards_dir = run_dir / "cards"
    slots_files = list(cards_dir.glob("*.card_slots.json"))
    if not slots_files:
        print(f"error: no card_slots.json under {cards_dir}", file=sys.stderr)
        return 2

    slots = json.loads(slots_files[0].read_text(encoding="utf-8"))
    meta = json.loads((run_dir / "meta" / "run.json").read_text(encoding="utf-8"))

    targets = collect_priority_targets(slots, args.top_n)

    envelope = {
        "schema_version": 1,
        "run_id": meta.get("run_id"),
        "ticker": args.ticker or meta.get("ticker"),
        "period": args.period or meta.get("fiscal_period"),
        "top_n": args.top_n,
        "engine_note": "Backend agent (post_card_auditor) fills `verification`, `source_url`, `source_value`, `notes` for each target via host web tools.",
        "targets": targets,
        "status": "pending" if targets else "no_targets",
    }

    out_path = Path(args.out) if args.out else run_dir / "validation" / "web_third_check.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(envelope, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
