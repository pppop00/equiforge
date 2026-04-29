"""Extract the locked HTML skeleton from skills_repo/er/agents/report_writer_{cn,en}.md.

Wrapper around ER's scripts/extract_report_template.py. Writes the skeleton into
the per-run research/ folder (or wherever --out-dir says).

Usage:
    python tools/research/extract_template.py --lang cn --run-dir <path>
    python tools/research/extract_template.py --lang en --out-dir /custom/path
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
    p.add_argument("--lang", required=True, choices=["cn", "en"])
    p.add_argument("--run-dir", default=None, help="Run directory; output goes to <run_dir>/research/")
    p.add_argument("--out-dir", default=None, help="Override output directory")
    p.add_argument("--filename", default=None, help="Override output filename (defaults to _locked_<lang>_skeleton.html)")
    p.add_argument("--sha256", action="store_true", help="Print SHA256 of extracted bytes")
    args = p.parse_args(argv)

    if args.out_dir:
        out_dir = Path(args.out_dir).resolve()
    elif args.run_dir:
        out_dir = (Path(args.run_dir) / "research").resolve()
    else:
        print("error: provide --run-dir or --out-dir", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    fname = args.filename or f"_locked_{args.lang}_skeleton.html"
    out_path = out_dir / fname

    er_root = find_skill_root("er")
    extractor = script_path("er", "scripts", "extract_report_template.py")

    cmd = [python_exec(), str(extractor), "--lang", args.lang, "-o", str(out_path)]
    if args.sha256:
        cmd.append("--sha256")
    result = subprocess.run(cmd, cwd=str(er_root), capture_output=True, text=True, check=False)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode == 0:
        print(str(out_path))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
