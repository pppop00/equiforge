"""Run EP's Validator 1 (skills_repo/ep/scripts/validate_cards.py) from the EP repo root.

EP's validator imports from generate_social_cards via a relative scripts/ layout, so cwd
must be the EP repo root.

This wrapper also writes a structured `validator1_report.json` (under the run's `cards/`
directory by default, or wherever `--report-out` points). The report file is the artifact
`workflow_meta.json -> P10_validator1.produces` promises, and is what the phase-advance
watchdog (`tools/io/advance.py`) checks for. Before this wrapper wrote the report, the
contract claimed the file existed but no code wrote it — the watchdog therefore blocked
runs that had actually passed validation, and downstream callers had no machine-readable
verdict to reason about (Codex P1#3).

Usage:
    python tools/photo/validate_cards.py \
        --input <run_dir>/research/Apple_Research_CN.html \
        --slots <run_dir>/cards/Apple_Research_CN.card_slots.json \
        --brand "金融豹" \
        --palette <confirmed_palette>

By default the report lands next to the slots file as `<slots_parent>/validator1_report.json`
(matching workflow_meta.json's declared produces path). Pass `--report-out` to override.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
from _common import find_skill_root, python_exec, script_path  # noqa: E402
from validate_metric_basis import validate_registry  # noqa: E402


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _maybe_run_metadata(slots_path: Path) -> dict:
    """If the slots path is inside a run dir, harvest run_id + ticker from meta/run.json."""
    parent = slots_path.parent
    for _ in range(4):  # walk up at most 4 levels
        candidate = parent / "meta" / "run.json"
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return {
                    "run_id": data.get("run_id"),
                    "ticker": data.get("ticker"),
                    "fiscal_period": data.get("fiscal_period"),
                }
            except json.JSONDecodeError:
                return {}
        if parent.parent == parent:
            break
        parent = parent.parent
    return {}


def _card4_formula_substitution_issues(slots_path: Path) -> list[str]:
    """Historical schema-v3/v4 gate for CFA formula substitution.

    EP's base validator guarantees that `cfa_lens.formula` looks like a
    formula and `company_calculation` contains at least one digit. That still
    permits a bad card where the formula is "FCF yield = FCF / market cap" but
    the company calculation only plugs in FCF, omitting the denominator and
    result. This wrapper catches that Anamnesis-specific content gap without
    editing the pinned EP submodule in-place.
    """
    try:
        raw = json.loads(slots_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    if not isinstance(raw, dict):
        return []
    if int(raw.get("schema_version") or 0) >= 5:
        return []
    lens = raw.get("cfa_lens")
    if not isinstance(lens, dict):
        return []

    formula = str(lens.get("formula") or "")
    calc_raw = lens.get("company_calculation")
    if isinstance(calc_raw, list):
        calc_lines = [str(x) for x in calc_raw if str(x).strip()]
    elif isinstance(calc_raw, str):
        calc_lines = [calc_raw]
    else:
        calc_lines = []
    calc_text = " ".join(calc_lines)
    if not formula or not calc_text:
        return []

    issues: list[str] = []
    formula_lower = formula.lower()
    formula_is_division = "/" in formula or "÷" in formula or "除以" in formula
    formula_mentions_market_cap = (
        "市值" in formula
        or "market cap" in formula_lower
        or "equity value" in formula_lower
    )
    if formula_is_division and formula_mentions_market_cap:
        if not ("市值" in calc_text or "market cap" in calc_text.lower() or "equity value" in calc_text.lower()):
            issues.append(
                "Card 4 cfa_lens.company_calculation must plug the denominator "
                "(市值 / market cap) when formula divides by market cap."
            )
        numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", calc_text.replace(",", ""))
        if len(numbers) < 2:
            issues.append(
                "Card 4 cfa_lens.company_calculation must contain at least two "
                "numeric operands for a market-cap division formula."
            )
        if "%" not in calc_text and "收益率" not in calc_text and "yield" not in calc_text.lower():
            issues.append(
                "Card 4 cfa_lens.company_calculation must show the computed "
                "yield/result for a market-cap division formula."
            )

    return issues


def _metric_basis_issues(slots_path: Path) -> list[str]:
    """For schema v5, require registry coverage and resolve calculation basis ids."""
    try:
        slots = json.loads(slots_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    if not isinstance(slots, dict) or slots.get("schema_version") != 5:
        return []
    run_dir = slots_path.parent
    for _ in range(4):
        basis_path = run_dir / "research" / "metric_basis.json"
        if basis_path.exists():
            break
        if run_dir.parent == run_dir:
            basis_path = None
            break
        run_dir = run_dir.parent
    else:
        basis_path = None
    if basis_path is None or not basis_path.exists():
        return ["schema v5 requires research/metric_basis.json for calculation and comparability checks"]
    try:
        registry = json.loads(basis_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"unable to read metric basis registry: {exc}"]
    stem = slots_path.name.removesuffix(".card_slots.json")
    notes_path = slots_path.with_name(f"{stem}.card_slots_worker_notes.json")
    notes = None
    if notes_path.exists():
        try:
            notes = json.loads(notes_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return [f"unable to read claim evidence sidecar for basis validation: {exc}"]
    return validate_registry(registry, notes)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--input", required=True, help="absolute path to *_Research_{CN,EN}.html")
    p.add_argument("--slots", required=True, help="absolute path to card_slots.json (file) or its parent dir")
    p.add_argument("--brand", default="金融豹")
    p.add_argument("--palette", required=True, choices=["macaron", "default", "b", "c"])
    p.add_argument("--allow-no-logo", action="store_true",
                   help="Only when customer explicitly waived logo")
    p.add_argument("--report-out", default=None,
                   help="Where to write validator1_report.json. Defaults to "
                        "<slots-parent>/validator1_report.json.")
    args = p.parse_args(argv)

    ep_root = find_skill_root("ep")
    validator = script_path("ep", "scripts", "validate_cards.py")

    cmd = [
        python_exec(),
        str(validator),
        "--input", args.input,
        "--slots", args.slots,
        "--brand", args.brand,
        "--palette", args.palette,
    ]
    if args.allow_no_logo:
        cmd.append("--allow-no-logo")

    result = subprocess.run(cmd, cwd=str(ep_root), capture_output=True, text=True, check=False)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)

    # Resolve report destination. EP's validator accepts a slots file OR its parent
    # directory; in either case the report co-locates with the slots-bearing directory.
    slots_path = Path(args.slots).resolve()
    slots_parent = slots_path if slots_path.is_dir() else slots_path.parent
    report_path = Path(args.report_out).resolve() if args.report_out else (
        slots_parent / "validator1_report.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)

    run_meta = _maybe_run_metadata(slots_path if slots_path.is_file() else slots_parent)

    # EP's validator emits issues to stderr on failure; capture them line-by-line for
    # downstream consumers. We keep the full stdout/stderr too for audit replay.
    issues = []
    if result.returncode != 0:
        for line in result.stderr.splitlines():
            line = line.strip()
            if line:
                issues.append(line)
    extra_issues = []
    if slots_path.is_file():
        extra_issues = _card4_formula_substitution_issues(slots_path)
        extra_issues.extend(_metric_basis_issues(slots_path))
        issues.extend(extra_issues)
    effective_returncode = 1 if result.returncode != 0 or extra_issues else 0

    report = {
        "schema_version": 1,
        "ts": _now_iso(),
        "run_id": run_meta.get("run_id"),
        "ticker": run_meta.get("ticker"),
        "tool": "tools/photo/validate_cards.py (skills_repo/ep/scripts/validate_cards.py)",
        "status": "pass" if effective_returncode == 0 else "fail",
        "exit_code": effective_returncode,
        "ep_exit_code": result.returncode,
        "palette": args.palette,
        "brand": args.brand,
        "card_schema": "v5",
        "allow_no_logo": bool(args.allow_no_logo),
        "input_html": args.input,
        "slots_path": str(slots_path),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "issues": issues,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Print the path on stderr (so JSON-consuming callers can still grep stdout cleanly).
    print(f"validator1_report.json -> {report_path}", file=sys.stderr)

    return effective_returncode


if __name__ == "__main__":
    raise SystemExit(main())
