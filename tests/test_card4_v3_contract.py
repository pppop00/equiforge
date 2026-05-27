"""Integration tests for the schema_version=3 Card-4 contract.

These pin the seam between EP (Equity Photo Skill) and the anamnesis harness
after the Card-4 redesign:

  - the `cfa_lens.takeaway` slot has been retired
  - `cfa_lens.formula` and `cfa_lens.company_calculation` are the new hard-rule
    Card-4 slots
  - `cfa_lens.company_calculation` is the new analyst-authority slot (was
    `cfa_lens.different_angle_insight` in v2)
  - the DB schema gained two columns: `cfa_lens_formula`, `cfa_lens_calculation`

Static-text / source-text checks only — they intentionally do not invoke EP.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / rel_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_card4_formula_in_priority_paths() -> None:
    web = _load_module("web_third_check_for_card4_test", "tools/audit/web_third_check.py")
    paths = list(web.PRIORITY_PATHS)
    assert "card_slots.cfa_lens.formula" in paths, (
        "tools/audit/web_third_check.PRIORITY_PATHS is missing "
        "'card_slots.cfa_lens.formula' — the new Card-4 formula slot will "
        "skip layer-3 web re-verification."
    )
    assert "card_slots.cfa_lens.company_calculation" in paths, (
        "tools/audit/web_third_check.PRIORITY_PATHS is missing "
        "'card_slots.cfa_lens.company_calculation' — the v3 authority slot "
        "will skip layer-3 web re-verification."
    )


def test_card4_authority_slot_is_company_calculation() -> None:
    voice_gate_src = (PROJECT_ROOT / "tools" / "photo" / "voice_gate.py").read_text(
        encoding="utf-8"
    )
    assert "cfa_lens.company_calculation" in voice_gate_src, (
        "tools/photo/voice_gate.py no longer references the v3 authority slot "
        "'cfa_lens.company_calculation'. The voice gate must surface the new "
        "authority slot so reviewers know where the analyst-quote requirement "
        "lives."
    )
    # The pre-v3 authority slot must not still be advertised as authority.
    lowered = voice_gate_src.lower()
    if "different_angle_insight" in lowered:
        ctx_idx = lowered.index("different_angle_insight")
        window = lowered[max(0, ctx_idx - 80) : ctx_idx + 80]
        assert "authority" not in window, (
            "tools/photo/voice_gate.py still describes "
            "'cfa_lens.different_angle_insight' as the authority slot. The v3 "
            "redesign moved authority to 'cfa_lens.company_calculation'."
        )


def test_card4_takeaway_slot_absent_from_db_writes() -> None:
    src = (PROJECT_ROOT / "tools" / "db" / "index_run.py").read_text(encoding="utf-8")
    # Strip block comments so doc-comments referencing the retired slot don't
    # falsely trip this gate. Anything starting with '#' through end of line
    # is a comment in Python and not executed.
    code_lines = []
    for raw in src.splitlines():
        stripped = raw.lstrip()
        if stripped.startswith("#"):
            continue
        # Drop trailing inline comments too.
        if "#" in raw:
            # Naive but sufficient: cut at first '#' not inside a string. The
            # index_run.py source does not use '#' inside strings on lines that
            # would otherwise reference these slot keys.
            raw = raw.split("#", 1)[0]
        code_lines.append(raw)
    executable = "\n".join(code_lines)
    assert "takeaway" not in executable, (
        "tools/db/index_run.py still references 'takeaway' in executable code. "
        "The v3 Card-4 redesign retired cfa_lens.takeaway entirely — DB writes "
        "must not pull from it."
    )


def test_card4_new_db_columns_declared() -> None:
    schema_src = (PROJECT_ROOT / "db" / "schema" / "001_init.sql").read_text(
        encoding="utf-8"
    )
    assert "cfa_lens_formula" in schema_src, (
        "db/schema/001_init.sql is missing the cfa_lens_formula column. "
        "The v3 Card-4 redesign added a dedicated column for cfa_lens.formula."
    )
    assert "cfa_lens_calculation" in schema_src, (
        "db/schema/001_init.sql is missing the cfa_lens_calculation column. "
        "The v3 Card-4 redesign added a dedicated column for "
        "cfa_lens.company_calculation."
    )
