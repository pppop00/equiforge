"""Shared helpers for tools/research/ and tools/photo/ wrappers.

These wrappers shell out only to the SHA-pinned upstream ER/EP submodules under
skills_repo/{er,ep}/. They deliberately do not fall back to sibling working
copies: Anamnesis must consume explicit submodule snapshots so local report/card
experiments cannot silently affect, or be affected by, the standalone ER/EP repos.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_REPO = PROJECT_ROOT / "skills_repo"


def find_skill_root(name: str) -> Path:
    """Resolve the absolute path of an upstream skill repo (er or ep)."""
    if name not in {"er", "ep"}:
        raise ValueError(f"unknown skill name: {name!r}")
    candidate = SKILLS_REPO / name
    if (candidate / "SKILL.md").exists():
        return candidate.resolve()
    raise FileNotFoundError(
        f"cannot locate {name!r} skill submodule at {candidate}. "
        f"Run `git submodule update --init --recursive` from {PROJECT_ROOT}; "
        "do not use sibling ER/EP working copies as runtime fallbacks."
    )


def script_path(skill: str, *parts: str) -> Path:
    p = find_skill_root(skill).joinpath(*parts)
    if not p.exists():
        raise FileNotFoundError(f"missing script: {p}")
    return p


def python_exec() -> str:
    """Use the same interpreter that's running this wrapper."""
    return sys.executable or "python3"
