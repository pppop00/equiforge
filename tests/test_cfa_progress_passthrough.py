"""Schema v5 removes CFA progress from all active wrapper CLIs and argv."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest


class Capture:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
        self.calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "", "")


@pytest.mark.parametrize("module_name", ["validate_cards", "render_cards", "voice_gate"])
def test_wrappers_reject_removed_cfa_progress_flag(module_name: str, tmp_path: Path) -> None:
    module = __import__(f"tools.photo.{module_name}", fromlist=[module_name])
    with pytest.raises(SystemExit) as exc:
        module.main([
            "--input", str(tmp_path / "report.html"),
            "--slots", str(tmp_path / "slots.json"),
            "--palette", "macaron",
            "--cfa-progress", "Level 2",
        ])
    assert exc.value.code == 2


@pytest.mark.parametrize("module_name", ["validate_cards", "render_cards", "voice_gate"])
def test_wrapper_source_has_no_active_cfa_progress_option(module_name: str) -> None:
    module = __import__(f"tools.photo.{module_name}", fromlist=[module_name])
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "p.add_argument(\"--cfa-progress\"" not in source
