"""Validate equiforge's workflow_meta.json contract.

Default: validates equiforge's own root workflow_meta.json (the fusion contract that
the orchestrator drives). Pass --target er to delegate to skills_repo/er's own
validator over ER's contract instead — those are different schemas and must not be
mixed.

Usage:
    python tools/research/validate_workflow_meta.py                     # validate equiforge root
    python tools/research/validate_workflow_meta.py --meta path/to/file # validate a specific file as equiforge schema
    python tools/research/validate_workflow_meta.py --target er         # delegate to ER's validator over ER's own meta
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _common import find_skill_root, python_exec, script_path  # type: ignore[import-not-found]

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Equiforge fusion-contract requirements. Keep in sync with workflow_meta.json shape.
REQUIRED_TOP_LEVEL = [
    "schema_version",
    "name",
    "phases",
    "subagent_concurrency_cap",
    "subagent_timeouts_seconds",
    "submodules",
    "memory_files",
    "freeze_system_prompt_at",
    "system_prompt_audit_path",
]

REQUIRED_PHASE_KEYS = ["id", "produces", "blocking", "interactive", "parallelism"]
ALLOWED_PARALLELISM = {"sequential", "parallel"}
REQUIRED_TIMEOUT_FAMILIES = {"research", "photo", "qc", "audit"}


def _err(msg: str) -> None:
    print(f"  ✗ {msg}", file=sys.stderr)


def validate_equiforge_meta(meta_path: Path) -> int:
    if not meta_path.exists():
        print(f"error: not found: {meta_path}", file=sys.stderr)
        return 2

    try:
        meta = json.loads(meta_path.read_text())
    except json.JSONDecodeError as e:
        print(f"error: {meta_path} is not valid JSON: {e}", file=sys.stderr)
        return 2

    print(f"validating equiforge contract: {meta_path}")
    errors = 0

    for key in REQUIRED_TOP_LEVEL:
        if key not in meta:
            _err(f"missing top-level key: {key!r}")
            errors += 1

    phases = meta.get("phases")
    if not isinstance(phases, list) or not phases:
        _err("'phases' must be a non-empty array")
        errors += 1
        phases = []

    seen_ids: set[str] = set()
    for i, phase in enumerate(phases):
        prefix = f"phase[{i}]"
        if not isinstance(phase, dict):
            _err(f"{prefix} is not an object")
            errors += 1
            continue
        pid = phase.get("id")
        if pid:
            prefix = f"phase {pid!r}"
            if pid in seen_ids:
                _err(f"duplicate phase id: {pid!r}")
                errors += 1
            seen_ids.add(pid)

        for k in REQUIRED_PHASE_KEYS:
            if k not in phase:
                _err(f"{prefix} missing required key: {k!r}")
                errors += 1

        par = phase.get("parallelism")
        if par is not None and par not in ALLOWED_PARALLELISM:
            _err(f"{prefix} parallelism={par!r} not in {sorted(ALLOWED_PARALLELISM)}")
            errors += 1

        if par == "parallel" and "agents" not in phase:
            _err(f"{prefix} parallelism='parallel' but no 'agents' array")
            errors += 1

        # A phase must drive *something*: an agent, a list of agents, a tool,
        # or be explicitly marked inline (orchestrator runs it directly).
        if not any(k in phase for k in ("agent", "agents", "tool")) and not phase.get("inline"):
            _err(f"{prefix} declares no executor (need 'agent' / 'agents' / 'tool' / 'inline: true')")
            errors += 1

    # retry_to targets must reference known phase IDs.
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        target = phase.get("retry_to")
        if target and target not in seen_ids:
            _err(f"phase {phase.get('id')!r} retry_to={target!r} is not a known phase id")
            errors += 1

    timeouts = meta.get("subagent_timeouts_seconds", {})
    if isinstance(timeouts, dict):
        missing = REQUIRED_TIMEOUT_FAMILIES - set(timeouts)
        if missing:
            _err(f"subagent_timeouts_seconds missing: {sorted(missing)}")
            errors += 1

    submodules = meta.get("submodules", {})
    if isinstance(submodules, dict):
        for expected in ("skills_repo/er", "skills_repo/ep"):
            if expected not in submodules:
                _err(f"submodules missing entry: {expected!r}")
                errors += 1

    if errors:
        print(f"\nFAIL: {errors} error(s) in {meta_path.name}", file=sys.stderr)
        return 1

    print(f"OK: {meta_path.name} ({len(phases)} phases, {len(seen_ids)} unique IDs)")
    return 0


def validate_er_meta(meta_path: str | None) -> int:
    er_root = find_skill_root("er")
    er_validator = script_path("er", "scripts", "validate_workflow_meta.py")
    target = meta_path or str(er_root / "workflow_meta.json")
    cmd = [python_exec(), str(er_validator), "--meta", target]
    try:
        result = subprocess.run(cmd, cwd=str(er_root), capture_output=True, text=True, check=False)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument(
        "--target",
        choices=["equiforge", "er"],
        default="equiforge",
        help="Which contract to validate. Default 'equiforge' validates this repo's root workflow_meta.json.",
    )
    p.add_argument(
        "--meta",
        default=None,
        help="Path to workflow_meta.json. If omitted, validates the default for the chosen target.",
    )
    args = p.parse_args(argv)

    if args.target == "er":
        return validate_er_meta(args.meta)

    meta_path = Path(args.meta) if args.meta else PROJECT_ROOT / "workflow_meta.json"
    return validate_equiforge_meta(meta_path)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
