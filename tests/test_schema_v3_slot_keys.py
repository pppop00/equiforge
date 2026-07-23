"""Lock schema-v5 slot-to-card OCR routing; legacy CFA slots stay inactive."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
EXPECTED = {
    "intro_sentence": 1,
    "one_minute_summary": 1,
    "metrics_row": 1,
    "industry_paragraph": 2,
    "background_bullets": 2,
    "porter_scores": 2,
    "porter_evidence": 2,
    "five_year_arc": 3,
    "financial_metrics_panel": 3,
    "company_quality": 4,
    "country_lens": 5,
}


def _module():
    spec = importlib.util.spec_from_file_location("ocr_schema_v5", ROOT / "tools/audit/ocr_cards.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schema_v5_slots_route_to_expected_cards() -> None:
    assert _module().SLOT_TO_CARD == EXPECTED


def test_cfa_and_archived_slots_are_not_active_ocr_inputs() -> None:
    mapping = _module().SLOT_TO_CARD
    for key in ("cfa_lens", "company_focus_paragraph", "recent_financial_highlights", "revenue_explainer_points"):
        assert key not in mapping


def test_ocr_uses_range_tolerance_and_ignores_provenance_dates() -> None:
    module = _module()
    assert module.value_appears_in_text(4178.0, "FCFF 4173亿")
    assert module.value_appears_in_text(23.7, "现金流同比下降2Z3.7%")
    # Tesseract often drops the decimal on large display metrics.
    assert module.value_appears_in_text(29.6, "784 |296 |1.2x")
    assert module.value_appears_in_text(78.4, "784 |296 |1.2x")

    slots = {
        "company_quality": {
            "valuation": {
                "metrics": [{"value": "不可比", "as_of_date": "2026-07-13"}]
            }
        }
    }
    numerics = module.collect_card_numerics(slots)[4]
    assert numerics == []
