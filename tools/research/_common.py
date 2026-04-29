"""Shared helpers for tools/research/ and tools/photo/ wrappers.

These wrappers shell out to the upstream ER/EP scripts living under skills_repo/{er,ep}/.
If the submodule is not yet initialised, fall back to the sibling directories at the
workspace root (../Equity Research Skill/, ../Equity Photo Skill/) so development can
proceed before `git submodule update --init` runs.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_REPO = PROJECT_ROOT / "skills_repo"

# Sibling locations for pre-submodule development on the local machine.
# Once `.gitmodules` is initialised these are no longer used.
LOCAL_FALLBACKS = {
    "er": Path("/Users/pppop/Desktop/Projects/Skills/Equity Research Skill"),
    "ep": Path("/Users/pppop/Desktop/Projects/Skills/Equity Photo Skill"),
}


def find_skill_root(name: str) -> Path:
    """Resolve the absolute path of an upstream skill repo (er or ep)."""
    if name not in {"er", "ep"}:
        raise ValueError(f"unknown skill name: {name!r}")
    candidate = SKILLS_REPO / name
    if (candidate / "SKILL.md").exists():
        return candidate.resolve()
    fallback = LOCAL_FALLBACKS[name]
    if (fallback / "SKILL.md").exists():
        return fallback.resolve()
    raise FileNotFoundError(
        f"cannot locate {name!r} skill — neither {candidate} nor {fallback} has SKILL.md. "
        f"Run `git submodule update --init --recursive` from {PROJECT_ROOT}."
    )


def script_path(skill: str, *parts: str) -> Path:
    p = find_skill_root(skill).joinpath(*parts)
    if not p.exists():
        raise FileNotFoundError(f"missing script: {p}")
    return p


def python_exec() -> str:
    """Use the same interpreter that's running this wrapper."""
    return sys.executable or "python3"
