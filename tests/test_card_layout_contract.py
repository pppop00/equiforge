"""Lock the 4-card filename contract across every surface that names them.

The post-bump EP submodule emits four PNGs (cover / Porter / 5-year + recent
financials / CFA lens). If any surface (workflow_meta produces, the render
wrapper's EXPECTED_CARD_FILES, the OCR wrapper's CARD_FILE_TO_INDEX) drifts
from the agreed filename list, a real run will fail in a way that's hard to
trace back to the contract — so we test all three surfaces independently with
one assertion each, and the failure message names the surface.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_FILENAMES = (
    "01_cover.png",
    "02_porter.png",
    "03_five_year_financials.png",
    "04_cfa_lens.png",
)
EXPECTED_PRODUCES = tuple(f"cards/{name}" for name in EXPECTED_FILENAMES)


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workflow_meta_p11_produces_lists_the_four_cards() -> None:
    """workflow_meta.json P11_render.produces must exactly equal the 4-card path list."""
    meta = json.loads((PROJECT_ROOT / "workflow_meta.json").read_text(encoding="utf-8"))
    phases = meta.get("phases") or meta.get("phase_order") or []
    p11 = next((p for p in phases if isinstance(p, dict) and p.get("id") == "P11_render"), None)
    assert p11 is not None, "workflow_meta.json has no P11_render phase"
    produces = tuple(p11.get("produces") or ())
    assert produces == EXPECTED_PRODUCES, (
        f"workflow_meta.json P11_render.produces drifted from the 4-card contract.\n"
        f"  expected: {EXPECTED_PRODUCES}\n"
        f"  got:      {produces}"
    )


def test_render_cards_expected_card_files_matches_contract() -> None:
    """tools/photo/render_cards.EXPECTED_CARD_FILES must equal the 4-card list."""
    render_cards = _load_module(
        "render_cards_for_contract_test",
        PROJECT_ROOT / "tools" / "photo" / "render_cards.py",
    )
    assert tuple(render_cards.EXPECTED_CARD_FILES) == EXPECTED_FILENAMES, (
        f"tools/photo/render_cards.EXPECTED_CARD_FILES drifted.\n"
        f"  expected: {EXPECTED_FILENAMES}\n"
        f"  got:      {tuple(render_cards.EXPECTED_CARD_FILES)}"
    )


def test_ocr_cards_file_to_index_has_exactly_four_entries() -> None:
    """tools/audit/ocr_cards.CARD_FILE_TO_INDEX must be a 4-entry dict mapping
    each contract filename to 1..4."""
    ocr_cards = _load_module(
        "ocr_cards_for_contract_test",
        PROJECT_ROOT / "tools" / "audit" / "ocr_cards.py",
    )
    mapping = ocr_cards.CARD_FILE_TO_INDEX
    expected = {name: i for i, name in enumerate(EXPECTED_FILENAMES, start=1)}
    assert mapping == expected, (
        f"tools/audit/ocr_cards.CARD_FILE_TO_INDEX drifted.\n"
        f"  expected: {expected}\n"
        f"  got:      {dict(mapping)}"
    )
