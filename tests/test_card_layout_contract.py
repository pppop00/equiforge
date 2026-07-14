"""Lock the continuous five-card filename contract across runtime surfaces."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_FILENAMES = (
    "01_cover.png", "02_porter.png", "03_five_year_financials.png",
    "04_company_quality.png", "05_country_lens.png",
)
EXPECTED_PRODUCES = tuple(f"cards/{name}" for name in EXPECTED_FILENAMES)


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workflow_meta_p11_produces_lists_five_cards() -> None:
    meta = json.loads((PROJECT_ROOT / "workflow_meta.json").read_text(encoding="utf-8"))
    p11 = next(p for p in meta["phases"] if p.get("id") == "P11_render")
    assert tuple(p11["produces"]) == EXPECTED_PRODUCES


def test_render_cards_expected_files_match_contract() -> None:
    render = _load_module("render_cards_contract", PROJECT_ROOT / "tools/photo/render_cards.py")
    assert tuple(render.EXPECTED_CARD_FILES) == EXPECTED_FILENAMES


def test_ocr_mapping_has_exact_five_card_contract() -> None:
    ocr = _load_module("ocr_cards_contract", PROJECT_ROOT / "tools/audit/ocr_cards.py")
    assert ocr.CARD_FILE_TO_INDEX == {
        name: index for index, name in enumerate(EXPECTED_FILENAMES, start=1)
    }
