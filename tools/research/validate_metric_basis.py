"""Validate the Metric Basis Registry and claim references.

Usage:
    python tools/research/validate_metric_basis.py --run-dir <run_dir>
    python tools/research/validate_metric_basis.py --metric-basis <metric_basis.json> \
        [--worker-notes <card_slots_worker_notes.json>] [--out <report.json>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_METRIC_KEYS = {
    "fcf",
    "roe",
    "capex",
    "net_debt",
    "fiscal_year",
    "currency_unit",
    "geographic_revenue",
    "valuation",
}
COMPARABILITY = {"comparable", "adjusted", "not_comparable"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def validate_registry(registry: dict, worker_notes: dict | None = None) -> list[str]:
    issues: list[str] = []
    if registry.get("schema_version") != 1:
        issues.append("metric_basis.schema_version must be 1")
    bases = registry.get("bases")
    if not isinstance(bases, list) or not bases:
        return [*issues, "metric_basis.bases must be a non-empty array"]

    ids: set[str] = set()
    covered: set[str] = set()
    for idx, basis in enumerate(bases):
        prefix = f"metric_basis.bases[{idx}]"
        if not isinstance(basis, dict):
            issues.append(f"{prefix} must be an object")
            continue
        basis_id = _text(basis.get("basis_id"))
        metric_key = _text(basis.get("metric_key"))
        if not basis_id or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", basis_id):
            issues.append(f"{prefix}.basis_id must be stable lowercase id text")
        elif basis_id in ids:
            issues.append(f"{prefix}.basis_id is duplicated: {basis_id}")
        else:
            ids.add(basis_id)
        if metric_key:
            covered.add(metric_key)
        else:
            issues.append(f"{prefix}.metric_key is required")
        for field in ("company_label", "company_definition", "standardized_formula", "period"):
            if not _text(basis.get(field)):
                issues.append(f"{prefix}.{field} is required")
        if metric_key not in {"fiscal_year", "geographic_revenue"}:
            for field in ("currency", "unit"):
                if not _text(basis.get(field)):
                    issues.append(f"{prefix}.{field} is required")
        refs = basis.get("source_refs")
        if not isinstance(refs, list) or not refs:
            issues.append(f"{prefix}.source_refs must be non-empty")
        state = _text(basis.get("comparability"))
        if state not in COMPARABILITY:
            issues.append(f"{prefix}.comparability must be one of {sorted(COMPARABILITY)}")
        if state in {"adjusted", "not_comparable"} and not _text(basis.get("adjustment_note")):
            issues.append(f"{prefix}.adjustment_note is required when comparability={state}")

    for missing in sorted(REQUIRED_METRIC_KEYS - covered):
        issues.append(f"metric_basis missing required metric_key: {missing}")

    if isinstance(worker_notes, dict):
        claims = worker_notes.get("claims")
        if not isinstance(claims, list):
            issues.append("worker_notes.claims must be an array")
        else:
            for idx, claim in enumerate(claims):
                if not isinstance(claim, dict):
                    continue
                if claim.get("epistemic_type") != "analyst_calculation":
                    continue
                basis_id = _text(claim.get("basis_id"))
                if basis_id not in ids:
                    issues.append(
                        f"worker_notes.claims[{idx}].basis_id references unknown registry id: {basis_id!r}"
                    )
    return issues


def _first(pattern: str, root: Path) -> Path | None:
    matches = sorted(root.glob(pattern))
    return matches[0] if matches else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-dir")
    parser.add_argument("--metric-basis")
    parser.add_argument("--worker-notes")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    if not args.run_dir and not args.metric_basis:
        parser.error("one of --run-dir or --metric-basis is required")
    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else None
    basis_path = (
        Path(args.metric_basis).expanduser().resolve()
        if args.metric_basis
        else run_dir / "research" / "metric_basis.json"
    )
    notes_path = Path(args.worker_notes).expanduser().resolve() if args.worker_notes else None
    if notes_path is None and run_dir is not None:
        notes_path = _first("*.card_slots_worker_notes.json", run_dir / "cards")
    out_path = (
        Path(args.out).expanduser().resolve()
        if args.out
        else (run_dir / "validation" / "metric_basis_validation.json" if run_dir else basis_path.with_name("metric_basis_validation.json"))
    )

    load_issues: list[str] = []
    try:
        registry = json.loads(basis_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        load_issues.append(f"unable to load metric_basis.json: {exc}")
        registry = {}
    worker_notes = None
    if notes_path is not None and notes_path.exists():
        try:
            worker_notes = json.loads(notes_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            load_issues.append(f"unable to load worker notes: {exc}")
    issues = [*load_issues, *validate_registry(registry, worker_notes)]
    report = {
        "schema_version": 1,
        "status": "pass" if not issues else "fail",
        "metric_basis_path": str(basis_path),
        "worker_notes_path": str(notes_path) if notes_path else None,
        "required_metric_keys": sorted(REQUIRED_METRIC_KEYS),
        "issues": issues,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"metric_basis_validation.json -> {out_path}")
    if issues:
        for issue in issues:
            print(f"error: {issue}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
