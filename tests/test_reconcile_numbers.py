"""tools/audit/reconcile_numbers.py — number-by-number diff between card slots and research JSONs."""
from __future__ import annotations

import json
from pathlib import Path

from tools.audit import reconcile_numbers
from tools.audit._numerics import NumericToken, extract_numerics, within_tolerance


def _write_research(dir: Path, **files: dict) -> None:
    dir.mkdir(parents=True, exist_ok=True)
    for fname, payload in files.items():
        (dir / f"{fname}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_extract_numerics_pp_and_pct() -> None:
    toks = extract_numerics("毛利率 56.3%，同比 +5.2pp")
    values = sorted(t.value for t in toks)
    assert 5.2 in values
    assert 56.3 in values
    units = {t.unit for t in toks}
    assert "pct" in units
    assert "pp" in units


def test_within_tolerance_pct() -> None:
    a = NumericToken(raw="56.3%", value=56.3, unit="pct", context="")
    b = NumericToken(raw="56.5%", value=56.5, unit="pct", context="")
    ok, _ = within_tolerance(a, b)
    assert ok

    c = NumericToken(raw="60%", value=60.0, unit="pct", context="")
    ok2, _ = within_tolerance(a, c)
    assert not ok2


def test_reconcile_passes_when_card_value_matches_research(tmp_path: Path) -> None:
    research = tmp_path / "research"
    _write_research(
        research,
        financial_analysis={"executive_summary": "毛利率 56.3%，营收增速 12.5%。"},
        financial_data={"income_statement": {"yoy_revenue_pct": 12.5}},
    )
    slots = tmp_path / "card_slots.json"
    slots.write_text(json.dumps({
        "company_focus_paragraph": "毛利率 56.3%，营收同比增长 12.5%。",
    }, ensure_ascii=False), encoding="utf-8")

    out = tmp_path / "reconciliation.csv"
    summary = reconcile_numbers.reconcile(slots, research, out)
    assert summary["fails"] == 0, f"expected pass, got: {summary}"
    assert out.exists()


def test_reconcile_flags_fabricated_number(tmp_path: Path) -> None:
    research = tmp_path / "research"
    _write_research(
        research,
        financial_analysis={"executive_summary": "毛利率 56.3%，营收增速 12.5%。"},
        financial_data={"income_statement": {"yoy_revenue_pct": 12.5}},
    )
    # Card slot says 99.9% gross margin but research says 56.3%
    slots = tmp_path / "card_slots.json"
    slots.write_text(json.dumps({
        "company_focus_paragraph": "毛利率 99.9%，营收增长 12.5%。",
    }, ensure_ascii=False), encoding="utf-8")

    out = tmp_path / "reconciliation.csv"
    summary = reconcile_numbers.reconcile(slots, research, out)
    assert summary["fails"] >= 1, f"expected at least one fail, got: {summary}"
