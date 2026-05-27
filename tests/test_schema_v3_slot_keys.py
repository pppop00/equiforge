"""Lock the schema_version=3 slot-key shape the harness expects from EP.

`tools/audit/ocr_cards.SLOT_TO_CARD` is the single mapping that tells the OCR
layer (P12 layer 2) which card a given slot key lives on. The Card-4 redesign
(schema_version 2 → 3) merged the three CFA cream panels into one, deleted
the `cfa_lens.takeaway` slot, and added two new hard-rule slots
(`cfa_lens.formula` and `cfa_lens.company_calculation`).

If a deleted slot reappears here, somewhere in EP or the harness has regressed
to an older schema. If a new slot is missing, the OCR layer will silently
skip its numerics — masking real audit failures.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Slots that the schema_version=3 Card-4 redesign deleted (or that earlier
# cutovers deleted). None of these may appear in SLOT_TO_CARD any more.
DELETED_SLOTS = (
    "brand_statement",
    "brand_subheading",
    "judgement_paragraph",
    "post_content_lines",
    "post_title",
    "hashtags",
    "memory_points",
    "cta_line",
    "conclusion_block",
    "current_business_points",
    "future_watch_points",
    # v3 Card-4 redesign — the takeaway slot is gone entirely.
    "cfa_lens.takeaway",
)

# (slot_key, expected_card_index) for the schema_version=3 slots whose
# OCR-layer placement the harness relies on. Card 4 carries two new
# nested hard-rule slots in v3: `formula` and `company_calculation`.
EXPECTED_NEW_SLOTS = {
    "metrics_row": 1,
    "porter_evidence": 2,
    "five_year_arc": 3,
    "recent_financial_highlights": 3,
    "cfa_lens": 4,
    "cfa_lens.formula": 4,
    "cfa_lens.company_calculation": 4,
}


def _load_ocr_cards():
    spec = importlib.util.spec_from_file_location(
        "ocr_cards_for_schema_test",
        PROJECT_ROOT / "tools" / "audit" / "ocr_cards.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_deleted_slots_remain_in_slot_to_card() -> None:
    ocr = _load_ocr_cards()
    mapping = ocr.SLOT_TO_CARD
    found = [slot for slot in DELETED_SLOTS if slot in mapping]
    assert not found, (
        f"tools/audit/ocr_cards.SLOT_TO_CARD still references deleted "
        f"slots: {found}. Remove them from SLOT_TO_CARD so the OCR "
        f"layer stops mapping legacy data."
    )


def test_new_schema_v3_slots_present_on_expected_cards() -> None:
    ocr = _load_ocr_cards()
    mapping = ocr.SLOT_TO_CARD
    for slot, expected_card in EXPECTED_NEW_SLOTS.items():
        assert slot in mapping, (
            f"tools/audit/ocr_cards.SLOT_TO_CARD is missing schema_version=3 "
            f"slot {slot!r}. It should map to card {expected_card}."
        )
        assert mapping[slot] == expected_card, (
            f"tools/audit/ocr_cards.SLOT_TO_CARD[{slot!r}] = {mapping[slot]}, "
            f"expected {expected_card}. Misrouted slot will skip OCR coverage on "
            f"the wrong card."
        )
