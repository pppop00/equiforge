"""Fetch a company's SEC EDGAR bundle into <run_dir>/research/sec_edgar_bundle.json.

Wrapper around ER's scripts/sec_edgar_fetch.py.

The User-Agent email is required by SEC; pass it from agents/sec_email_gate.md output.
The email is NEVER persisted to db/equity_kb.sqlite (see MEMORY.md privacy invariants).

Usage:
    python tools/research/sec_edgar_fetch.py \
        --ticker AAPL \
        --user-agent "EquityFusionSkill/1.0 (you@example.com)" \
        --report-date 2026-04-28 \
        --run-dir <path>
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_skill_root, python_exec, script_path  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--ticker", required=True)
    p.add_argument("--user-agent", required=True, help='e.g. "EquityFusionSkill/1.0 (real@email.com)"')
    p.add_argument("--report-date", required=True, help="YYYY-MM-DD")
    p.add_argument("--run-dir", required=True)
    args = p.parse_args(argv)

    out = (Path(args.run_dir) / "research" / "sec_edgar_bundle.json").resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    er_root = find_skill_root("er")
    fetcher = script_path("er", "scripts", "sec_edgar_fetch.py")

    cmd = [
        python_exec(),
        str(fetcher),
        "--ticker", args.ticker,
        "--user-agent", args.user_agent,
        "--report-date", args.report_date,
        "-o", str(out),
    ]
    result = subprocess.run(cmd, cwd=str(er_root), capture_output=True, text=True, check=False)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode == 0:
        print(str(out))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
