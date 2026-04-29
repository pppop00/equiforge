"""Convenience wrapper that calls tools/io/run_dir.py and emits a phase_enter event.

Usage:
    python tools/research/workspace_bootstrap.py --company Apple --date 2026-04-28
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--company", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--run-id", default=None)
    p.add_argument("--output-root", default=None)
    args = p.parse_args(argv)

    cmd = [sys.executable, str(PROJECT_ROOT / "tools" / "io" / "run_dir.py"),
           "--company", args.company, "--date", args.date]
    if args.run_id:
        cmd += ["--run-id", args.run_id]
    if args.output_root:
        cmd += ["--output-root", args.output_root]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        return result.returncode
    run_dir = result.stdout.strip().splitlines()[-1]
    print(run_dir)

    event_cmd = [
        sys.executable, str(PROJECT_ROOT / "tools" / "io" / "event_log.py"),
        "--run-dir", run_dir,
        "--phase", "P0_intent",
        "--event", "phase_enter",
        "--payload", json.dumps({"company": args.company, "date": args.date}),
    ]
    subprocess.run(event_cmd, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
