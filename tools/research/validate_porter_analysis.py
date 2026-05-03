"""Validate porter_analysis.json shape.

Catches the failure mode where a perspective collapses into a single
``narrative`` string instead of the five per-force fields the report writer
expects. When the intermediate JSON loses force-level granularity, Phase 5
cannot produce the five-bullet QC-deliberation Porter list mandated by
``references/report_style_guide_cn.md`` / ``report_style_guide_en.md``;
the writer falls back to dumping the single string into ``.porter-text``.

This is a deterministic Phase 3 / Phase 5 gate. Run after Phase 3 (Porter
draft) and again before Phase 5 (report writing) so the writer is guaranteed
a per-force input.

Usage:
    python tools/research/validate_porter_analysis.py --run-dir <path>
    python tools/research/validate_porter_analysis.py --json <porter_analysis.json>

Exit codes:
    0 = pass
    1 = critical (schema does not match contract)
    2 = invocation error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PERSPECTIVES = ("company_perspective", "industry_perspective", "forward_perspective")
FORCES = ("supplier_power", "buyer_power", "new_entrants", "substitutes", "rivalry")
MIN_FORCE_CHARS = 20


def _is_int_1_to_5(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5


def validate_porter_analysis(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return {
            "status": "critical",
            "errors": ["porter_analysis.json root is not a JSON object"],
            "warnings": [],
        }

    for perspective in PERSPECTIVES:
        if perspective not in data:
            errors.append(f"missing perspective: {perspective}")
            continue
        node = data[perspective]
        if not isinstance(node, dict):
            errors.append(f"{perspective} is not an object")
            continue

        scores = node.get("scores")
        if not isinstance(scores, list) or len(scores) != 5:
            errors.append(f"{perspective}.scores must be a list of exactly 5 integers")
        else:
            for i, s in enumerate(scores):
                if not _is_int_1_to_5(s):
                    errors.append(
                        f"{perspective}.scores[{i}]={s!r} is not an integer in 1..5"
                    )

        if "narrative" in node and not any(f in node for f in FORCES):
            errors.append(
                f"{perspective} uses the deprecated flat-narrative shape "
                f"({{scores, narrative}}); writer cannot produce a five-bullet "
                f"Porter list from a single string. Restructure into the five "
                f"per-force keys: {', '.join(FORCES)}."
            )
            continue

        for force in FORCES:
            if force not in node:
                errors.append(f"{perspective}.{force} is missing")
                continue
            text = node[force]
            if not isinstance(text, str):
                errors.append(f"{perspective}.{force} is not a string")
                continue
            stripped = text.strip()
            if not stripped:
                errors.append(f"{perspective}.{force} is empty")
                continue
            if len(stripped) < MIN_FORCE_CHARS:
                warnings.append(
                    f"{perspective}.{force} is suspiciously short "
                    f"({len(stripped)} chars < {MIN_FORCE_CHARS}); writer needs "
                    f"enough analysis to produce a meaningful <li>."
                )

    return {
        "status": "critical" if errors else ("warn" if warnings else "pass"),
        "perspectives_required": list(PERSPECTIVES),
        "forces_required": list(FORCES),
        "errors": errors,
        "warnings": warnings,
    }


def _find_porter_json(run_dir: Path) -> Path | None:
    for candidate in (
        run_dir / "research" / "porter_analysis.json",
        run_dir / "porter_analysis.json",
    ):
        if candidate.exists():
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--run-dir", default=None)
    p.add_argument("--json", dest="json_path", default=None)
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    if args.run_dir:
        path = _find_porter_json(Path(args.run_dir).resolve())
        if path is None:
            result = {
                "status": "critical",
                "errors": [
                    f"porter_analysis.json not found under {args.run_dir} "
                    f"(looked in research/ and root)"
                ],
                "warnings": [],
            }
        else:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                result = {
                    "status": "critical",
                    "errors": [f"failed to parse {path}: {exc}"],
                    "warnings": [],
                }
            else:
                result = validate_porter_analysis(data)
                result["json_file"] = str(path)
    elif args.json_path:
        path = Path(args.json_path).resolve()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: failed to parse {path}: {exc}", file=sys.stderr)
            return 2
        result = validate_porter_analysis(data)
        result["json_file"] = str(path)
    else:
        print("error: provide --run-dir or --json", file=sys.stderr)
        return 2

    out_path = Path(args.out).resolve() if args.out else None
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "critical" else 1


if __name__ == "__main__":
    raise SystemExit(main())
