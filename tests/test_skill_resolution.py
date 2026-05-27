from __future__ import annotations

from pathlib import Path

import pytest

from tools.research import _common


def test_find_skill_root_resolves_only_pinned_submodule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills_repo = tmp_path / "skills_repo"
    er = skills_repo / "er"
    er.mkdir(parents=True)
    (er / "SKILL.md").write_text("---\nname: er\n---\n", encoding="utf-8")
    monkeypatch.setattr(_common, "SKILLS_REPO", skills_repo)

    assert _common.find_skill_root("er") == er.resolve()


def test_find_skill_root_does_not_fall_back_to_sibling_working_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills_repo = tmp_path / "skills_repo"
    sibling = tmp_path / "Equity Research Skill"
    sibling.mkdir()
    (sibling / "SKILL.md").write_text("---\nname: er\n---\n", encoding="utf-8")
    monkeypatch.setattr(_common, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(_common, "SKILLS_REPO", skills_repo)

    with pytest.raises(FileNotFoundError, match="submodule"):
        _common.find_skill_root("er")


def test_find_skill_root_rejects_unknown_skill_name() -> None:
    with pytest.raises(ValueError, match="unknown skill name"):
        _common.find_skill_root("rp")
