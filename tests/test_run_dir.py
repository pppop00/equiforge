"""tools/io/run_dir.py — bootstraps the per-run output directory."""
from __future__ import annotations

import json
from pathlib import Path

from tools.io import run_dir as run_dir_mod


def test_init_run_dir_creates_subfolders(tmp_path: Path) -> None:
    out_root = tmp_path / "out"
    rd = run_dir_mod.init_run_dir("Apple", "2026-04-28", run_id="testrun1", output_root=out_root)
    assert rd.exists()
    for sub in ("meta", "research", "cards", "cards/logo", "validation", "validation/ocr_dump",
                "db_export", "logs"):
        assert (rd / sub).exists(), f"missing {sub}"

    log = rd / "meta" / "run.jsonl"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["phase"] == "bootstrap"
    assert rec["event"] == "started"
    assert rec["payload"]["company"] == "Apple"
    assert rec["payload"]["slug"] == "Apple"
    assert rec["payload"]["run_id"] == "testrun1"

    run_json = json.loads((rd / "meta" / "run.json").read_text(encoding="utf-8"))
    assert run_json["run_id"] == "testrun1"
    assert run_json["company"] == "Apple"


def test_slugify_handles_unicode(tmp_path: Path) -> None:
    rd = run_dir_mod.init_run_dir("阿里巴巴", "2026-04-28", run_id="test2", output_root=tmp_path)
    # CJK characters get stripped — slug falls back to underscores or "Company"
    assert rd.name.endswith("_2026-04-28_test2")


def test_init_run_dir_refuses_overwrite(tmp_path: Path) -> None:
    out_root = tmp_path
    run_dir_mod.init_run_dir("Apple", "2026-04-28", run_id="dup", output_root=out_root)
    try:
        run_dir_mod.init_run_dir("Apple", "2026-04-28", run_id="dup", output_root=out_root)
    except FileExistsError:
        return
    raise AssertionError("expected FileExistsError on duplicate run_id")
