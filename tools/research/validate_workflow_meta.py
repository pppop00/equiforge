"""Run skills_repo/er/scripts/validate_workflow_meta.py over our own workflow_meta.json
or over ER's. Default: validate ER's contract (since the orchestrator runs phases that
ER defines).

Usage:
    python tools/research/validate_workflow_meta.py                       # ER's
    python tools/research/validate_workflow_meta.py --meta workflow_meta.json   # fusion's
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import find_skill_root, python_exec, script_path  # type: ignore[import-not-found]

import subprocess


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument(
        "--meta",
        default=None,
        help="Path to workflow_meta.json. If omitted, validates ER's own.",
    )
    args = p.parse_args(argv)

    er_root = find_skill_root("er")
    er_validator = script_path("er", "scripts", "validate_workflow_meta.py")

    meta_path = args.meta or str(er_root / "workflow_meta.json")

    cmd = [python_exec(), str(er_validator), "--meta", meta_path]
    try:
        result = subprocess.run(cmd, cwd=str(er_root), capture_output=True, text=True, check=False)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3

    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
