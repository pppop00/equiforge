"""Lock the `--cfa-progress` flag passthrough from the harness wrappers down to EP.

`tools/photo/validate_cards.py`, `tools/photo/voice_gate.py`, and
`tools/photo/render_cards.py` accept `--cfa-progress <str>` and must forward it
to the EP CLI (validate_cards / generate_social_cards). EP after the 4-card
cutover accepts it on both upstream scripts (mirrored). We test wrapper passthrough
shape so that if anyone ever drops the flag from argv construction, CI catches
it before a real run does.

We mock subprocess.run so the tests don't depend on the (still-old, pre-bump)
EP submodule actually supporting the flag.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, List

import pytest

from tools.io import run_dir as run_dir_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_run(tmp_path: Path) -> Path:
    rd = run_dir_mod.init_run_dir(
        "Apple", "2026-04-28", "cfaprog1",
        output_root=tmp_path, orchestrator_model="claude-opus-4-7",
    )
    (rd / "meta" / "run.json").write_text(
        json.dumps({"run_id": "cfaprog1", "ticker": "AAPL", "fiscal_period": "FY2026"}),
        encoding="utf-8",
    )
    return rd


def _seed_slots(rd: Path, *, with_worker_notes: bool) -> Path:
    slots = rd / "cards" / "Apple_Research_CN.card_slots.json"
    slots.parent.mkdir(parents=True, exist_ok=True)
    slots.write_text(json.dumps({"cover_company_name_cn": "苹果"}), encoding="utf-8")
    if with_worker_notes:
        sidecar = rd / "cards" / "Apple_Research_CN.card_slots_worker_notes.json"
        sidecar.write_text(json.dumps({"cfa_lens": {}}), encoding="utf-8")
    return slots


class _ArgvCapture:
    """A subprocess.run stand-in that records every argv it sees."""

    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.calls: List[List[str]] = []
        self._returncode = returncode
        self._stderr = stderr

    def __call__(self, cmd, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
        # cmd may be a list (the wrappers always pass a list)
        self.calls.append(list(cmd))
        return subprocess.CompletedProcess(
            args=cmd, returncode=self._returncode, stdout="", stderr=self._stderr,
        )


# ---------------------------------------------------------------------------
# validate_cards wrapper
# ---------------------------------------------------------------------------


def test_validate_cards_forwards_cfa_progress_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.photo import validate_cards as wrapper

    rd = _seed_run(tmp_path)
    slots = _seed_slots(rd, with_worker_notes=False)
    html = rd / "research" / "Apple_Research_CN.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text("<html></html>", encoding="utf-8")

    capture = _ArgvCapture(returncode=0)
    monkeypatch.setattr(wrapper, "find_skill_root", lambda *_: tmp_path)
    monkeypatch.setattr(wrapper, "script_path", lambda *a: tmp_path / "fake_ep_validator.py")
    monkeypatch.setattr(wrapper, "python_exec", lambda: "python3")
    monkeypatch.setattr(wrapper.subprocess, "run", capture)

    rc = wrapper.main([
        "--input", str(html),
        "--slots", str(slots),
        "--palette", "macaron",
        "--cfa-progress", "Level 2 - Fixed Income - Binomial Tree",
    ])
    assert rc == 0
    argv = capture.calls[0]
    assert "--cfa-progress" in argv, (
        f"validate_cards did not forward --cfa-progress to EP validator.\n  argv: {argv}"
    )
    idx = argv.index("--cfa-progress")
    assert argv[idx + 1] == "Level 2 - Fixed Income - Binomial Tree"


def test_validate_cards_omits_cfa_progress_when_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.photo import validate_cards as wrapper

    rd = _seed_run(tmp_path)
    slots = _seed_slots(rd, with_worker_notes=False)
    html = rd / "research" / "Apple_Research_CN.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text("<html></html>", encoding="utf-8")

    capture = _ArgvCapture(returncode=0)
    monkeypatch.setattr(wrapper, "find_skill_root", lambda *_: tmp_path)
    monkeypatch.setattr(wrapper, "script_path", lambda *a: tmp_path / "fake_ep_validator.py")
    monkeypatch.setattr(wrapper, "python_exec", lambda: "python3")
    monkeypatch.setattr(wrapper.subprocess, "run", capture)

    rc = wrapper.main([
        "--input", str(html),
        "--slots", str(slots),
        "--palette", "macaron",
    ])
    assert rc == 0
    argv = capture.calls[0]
    assert "--cfa-progress" not in argv, (
        f"validate_cards leaked --cfa-progress flag when none was passed.\n  argv: {argv}"
    )


# ---------------------------------------------------------------------------
# render_cards wrapper
# ---------------------------------------------------------------------------


def test_render_cards_forwards_cfa_progress_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.photo import render_cards as wrapper

    html = tmp_path / "Apple_Research_CN.html"
    html.write_text("<html></html>", encoding="utf-8")
    slots = tmp_path / "Apple_Research_CN.card_slots.json"
    slots.write_text("{}", encoding="utf-8")

    capture = _ArgvCapture(returncode=0)
    monkeypatch.setattr(wrapper, "find_skill_root", lambda *_: tmp_path)
    monkeypatch.setattr(wrapper, "script_path", lambda *a: tmp_path / "fake_ep_renderer.py")
    monkeypatch.setattr(wrapper, "python_exec", lambda: "python3")
    monkeypatch.setattr(wrapper.subprocess, "run", capture)

    rc = wrapper.main([
        "--input", str(html),
        "--slots", str(slots),
        "--palette", "macaron",
        "--cfa-progress", "Level 2 - Fixed Income - Binomial Tree",
        # No --output-root => the wrapper calls subprocess.run directly (single call path)
    ])
    assert rc == 0
    assert len(capture.calls) == 1, f"expected 1 subprocess call, got {len(capture.calls)}"
    argv = capture.calls[0]
    assert "--cfa-progress" in argv, (
        f"render_cards did not forward --cfa-progress to EP renderer.\n  argv: {argv}"
    )
    idx = argv.index("--cfa-progress")
    assert argv[idx + 1] == "Level 2 - Fixed Income - Binomial Tree", (
        f"render_cards forwarded --cfa-progress with wrong value: {argv[idx + 1]!r}"
    )


def test_render_cards_omits_cfa_progress_when_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.photo import render_cards as wrapper

    html = tmp_path / "Apple_Research_CN.html"
    html.write_text("<html></html>", encoding="utf-8")
    slots = tmp_path / "Apple_Research_CN.card_slots.json"
    slots.write_text("{}", encoding="utf-8")

    capture = _ArgvCapture(returncode=0)
    monkeypatch.setattr(wrapper, "find_skill_root", lambda *_: tmp_path)
    monkeypatch.setattr(wrapper, "script_path", lambda *a: tmp_path / "fake_ep_renderer.py")
    monkeypatch.setattr(wrapper, "python_exec", lambda: "python3")
    monkeypatch.setattr(wrapper.subprocess, "run", capture)

    rc = wrapper.main([
        "--input", str(html),
        "--slots", str(slots),
        "--palette", "macaron",
        # NO --cfa-progress
    ])
    assert rc == 0
    argv = capture.calls[0]
    assert "--cfa-progress" not in argv, (
        f"render_cards leaked --cfa-progress flag when none was passed.\n  argv: {argv}"
    )


# ---------------------------------------------------------------------------
# voice_gate wrapper
# ---------------------------------------------------------------------------


def test_voice_gate_forwards_cfa_progress_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.photo import voice_gate as wrapper

    rd = _seed_run(tmp_path)
    slots = _seed_slots(rd, with_worker_notes=True)
    html = rd / "research" / "Apple_Research_CN.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text("<html></html>", encoding="utf-8")

    capture = _ArgvCapture(returncode=0)
    monkeypatch.setattr(wrapper, "find_skill_root", lambda *_: tmp_path)
    monkeypatch.setattr(wrapper, "script_path", lambda *a: tmp_path / "fake_ep_validator.py")
    monkeypatch.setattr(wrapper, "python_exec", lambda: "python3")
    monkeypatch.setattr(wrapper.subprocess, "run", capture)

    rc = wrapper.main([
        "--input", str(html),
        "--slots", str(slots),
        "--palette", "macaron",
        "--cfa-progress", "Level 2 - Fixed Income - Binomial Tree",
    ])
    assert rc == 0
    argv = capture.calls[0]
    assert "--cfa-progress" in argv, (
        f"voice_gate did not forward --cfa-progress to EP validator.\n  argv: {argv}"
    )
    idx = argv.index("--cfa-progress")
    assert argv[idx + 1] == "Level 2 - Fixed Income - Binomial Tree"


def test_voice_gate_omits_cfa_progress_when_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.photo import voice_gate as wrapper

    rd = _seed_run(tmp_path)
    slots = _seed_slots(rd, with_worker_notes=True)
    html = rd / "research" / "Apple_Research_CN.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    html.write_text("<html></html>", encoding="utf-8")

    capture = _ArgvCapture(returncode=0)
    monkeypatch.setattr(wrapper, "find_skill_root", lambda *_: tmp_path)
    monkeypatch.setattr(wrapper, "script_path", lambda *a: tmp_path / "fake_ep_validator.py")
    monkeypatch.setattr(wrapper, "python_exec", lambda: "python3")
    monkeypatch.setattr(wrapper.subprocess, "run", capture)

    rc = wrapper.main([
        "--input", str(html),
        "--slots", str(slots),
        "--palette", "macaron",
    ])
    assert rc == 0
    argv = capture.calls[0]
    assert "--cfa-progress" not in argv, (
        f"voice_gate leaked --cfa-progress flag when none was passed.\n  argv: {argv}"
    )
