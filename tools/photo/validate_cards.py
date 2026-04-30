"""Run EP's Validator 1 (skills_repo/ep/scripts/validate_cards.py) from the EP repo root.

EP's validator imports from generate_social_cards via a relative scripts/ layout, so cwd
must be the EP repo root.

Usage:
    python tools/photo/validate_cards.py \
        --input <run_dir>/research/Apple_Research_CN.html \
        --slots <run_dir>/cards/Apple_Research_CN.card_slots.json \
        --brand "金融豹" \
        --palette <confirmed_palette>
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
from _common import find_skill_root, python_exec, script_path  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--input", required=True, help="absolute path to *_Research_{CN,EN}.html")
    p.add_argument("--slots", required=True, help="absolute path to card_slots.json (file) or its parent dir")
    p.add_argument("--brand", default="金融豹")
    p.add_argument("--palette", required=True, choices=["macaron", "default", "b", "c"])
    p.add_argument("--allow-no-logo", action="store_true",
                   help="Only when customer explicitly waived logo")
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
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
