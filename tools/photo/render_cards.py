"""Run EP's renderer (skills_repo/ep/scripts/generate_social_cards.py).

Always pass the SAME --palette as Validator 1 used. Default --output-root is the
per-run cards/ directory.

Usage:
    python tools/photo/render_cards.py \
        --input <run_dir>/research/Apple_Research_CN.html \
        --slots <run_dir>/cards/Apple_Research_CN.card_slots.json \
        --brand "金融豹" \
        --palette macaron \
        --output-root <run_dir>/cards
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
from _common import find_skill_root, python_exec, script_path  # noqa: E402


def _flatten_stem_dir(output_root: Path, stem: str) -> None:
    """Move <output_root>/<stem>/* up to <output_root>/, then remove the empty stem dir.

    The EP renderer always writes to output_root / stem (its batch-mode convention).
    For per-run cards/ folders we want a flat layout so downstream audit tools
    (tools/audit/ocr_cards.py, etc.) and end users find the PNGs at a predictable
    path. Files at the destination are overwritten — they should be byte-identical
    copies (e.g. the slots JSON).
    """
    inner = output_root / stem
    if not inner.is_dir():
        return
    for item in list(inner.iterdir()):
        dest = output_root / item.name
        if dest.exists():
            if dest.is_dir() and not dest.is_symlink():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        shutil.move(str(item), str(dest))
    try:
        inner.rmdir()
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--input", required=True)
    p.add_argument("--slots", required=True)
    p.add_argument("--brand", default="金融豹")
    p.add_argument("--palette", required=True, choices=["macaron", "default", "b", "c"])
    p.add_argument("--output-root", default=None,
                   help="Default: skills_repo/ep/output/<stem>/. Override to per-run cards/.")
    p.add_argument("--export-logical-size", action="store_true",
                   help="Export 1080x1350 instead of 2160x2700.")
    p.add_argument("--no-copy-slots", action="store_true",
                   help="Do not copy card_slots.json into the output dir.")
    args = p.parse_args(argv)

    ep_root = find_skill_root("ep")
    renderer = script_path("ep", "scripts", "generate_social_cards.py")

    cmd = [
        python_exec(),
        str(renderer),
        "--input", args.input,
        "--slots", args.slots,
        "--brand", args.brand,
        "--palette", args.palette,
    ]
    if args.output_root:
        cmd += ["--output-root", args.output_root]
    if args.export_logical_size:
        cmd.append("--export-logical-size")
    if args.no_copy_slots:
        cmd.append("--no-copy-slots")

    result = subprocess.run(cmd, cwd=str(ep_root), capture_output=True, text=True, check=False)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode == 0 and args.output_root:
        _flatten_stem_dir(Path(args.output_root).resolve(), Path(args.input).stem)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
