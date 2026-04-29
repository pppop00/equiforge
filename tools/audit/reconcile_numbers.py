"""P12 layer 1 — numerical reconciliation.

For every numeric token in <run_dir>/cards/*.card_slots.json, find a near-match
in <run_dir>/research/*.json. A token matches if normalised value is within
tolerance (per MEMORY.md). Mismatches → CSV row with status=fail.

Usage:
    python tools/audit/reconcile_numbers.py --run-dir <path>
    python tools/audit/reconcile_numbers.py --slots <slots> --research <dir> --out <csv>
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _numerics import NumericToken, extract_numerics, within_tolerance  # noqa: E402

RESEARCH_FILES = (
    "financial_data.json",
    "financial_analysis.json",
    "prediction_waterfall.json",
    "porter_analysis.json",
    "macro_factors.json",
    "edge_insights.json",
    "news_intel.json",
)


def walk_strings(node, path: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        yield path, str(node)


def load_research_numerics(research_dir: Path) -> list[NumericToken]:
    out: list[NumericToken] = []
    for fname in RESEARCH_FILES:
        path = research_dir / fname
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for jpath, text in walk_strings(data, fname):
            out.extend(extract_numerics(text, path=jpath))
    return out


def load_slot_numerics(slots_path: Path) -> list[NumericToken]:
    data = json.loads(slots_path.read_text(encoding="utf-8"))
    out: list[NumericToken] = []
    for jpath, text in walk_strings(data, "card_slots"):
        if jpath.endswith(".logo_asset_path"):
            continue
        out.extend(extract_numerics(text, path=jpath))
    return out


def best_match(t: NumericToken, pool: list[NumericToken]) -> tuple[NumericToken | None, dict]:
    best: tuple[NumericToken | None, dict] = (None, {})
    best_score = float("inf")
    for cand in pool:
        ok, info = within_tolerance(t, cand)
        if ok:
            return cand, {**info, "match": True}
        # rough scoring for nearest miss
        score = abs(t.value - cand.value) / (abs(t.value) + abs(cand.value) + 1.0)
        if score < best_score:
            best_score = score
            best = (cand, {**info, "match": False, "score": score})
    return best


def reconcile(slots_path: Path, research_dir: Path, out_csv: Path) -> dict:
    slot_tokens = load_slot_numerics(slots_path)
    research_tokens = load_research_numerics(research_dir)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fails = 0
    warns = 0
    rows: list[dict] = []
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["slot_path", "slot_value", "slot_unit", "slot_context", "match_path",
                          "match_value", "match_unit", "match_context", "status", "details"])
        for tok in slot_tokens:
            cand, info = best_match(tok, research_tokens)
            if info.get("match"):
                status = "pass"
            elif cand is None:
                status = "warn"  # nothing in research at all — could be a date or ordinal
                warns += 1
            else:
                status = "fail"
                fails += 1
            row = [tok.path, tok.value, tok.unit or "", tok.context,
                   getattr(cand, "path", "") if cand else "",
                   getattr(cand, "value", "") if cand else "",
                   getattr(cand, "unit", "") or "" if cand else "",
                   getattr(cand, "context", "") if cand else "",
                   status, json.dumps(info, ensure_ascii=False)]
            writer.writerow(row)
            rows.append({
                "slot_path": tok.path, "slot_value": tok.value, "slot_unit": tok.unit,
                "match_path": getattr(cand, "path", None) if cand else None,
                "match_value": getattr(cand, "value", None) if cand else None,
                "status": status,
            })

    return {
        "rows_checked": len(slot_tokens),
        "fails": fails,
        "warns": warns,
        "passes": len(slot_tokens) - fails - warns,
        "csv_path": str(out_csv),
        "status": "fail" if fails else ("warn" if warns else "pass"),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--run-dir", default=None)
    p.add_argument("--slots", default=None)
    p.add_argument("--research", default=None)
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
        candidates = list((run_dir / "cards").glob("*.card_slots.json"))
        if not candidates:
            print(f"error: no card_slots.json under {run_dir}/cards/", file=sys.stderr)
            return 2
        slots = candidates[0]
        research = run_dir / "research"
        out = run_dir / "validation" / "reconciliation.csv"
    else:
        if not (args.slots and args.research and args.out):
            print("error: provide --run-dir, or all of --slots --research --out", file=sys.stderr)
            return 2
        slots = Path(args.slots).resolve()
        research = Path(args.research).resolve()
        out = Path(args.out).resolve()

    summary = reconcile(slots, research, out)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
