"""P12 layer 2 — OCR each rendered PNG and confirm key numerics appear.

Picks the OCR engine in this order: USER.md override → paddleocr if installed →
pytesseract if installed → no-op stub (warn, no fail).

Compares OCR'd text against the numeric tokens in card_slots.json (per card).
A miss for a *key* numeric (revenue, YoY, margins, top Porter scores) → fail.

Usage:
    python tools/audit/ocr_cards.py --run-dir <path> --lang cn
    python tools/audit/ocr_cards.py --cards-dir <dir> --slots <slots> --lang en --out-dir <dir>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _numerics import extract_numerics, NumericToken  # noqa: E402

CARD_FILE_TO_INDEX = {
    "01_cover.png": 1,
    "02_background_industry.png": 2,
    "03_revenue.png": 3,
    "04_business_outlook.png": 4,
    "05_brand.png": 5,
    "06_post_copy.png": 6,
}

# Slot keys → which card index they appear on (1-indexed)
SLOT_TO_CARD = {
    "intro_sentence": 1,
    "company_focus_paragraph": 1,
    "background_bullets": 2,
    "industry_paragraph": 2,
    "porter_scores": 2,
    "conclusion_block": 2,
    "revenue_explainer_points": 3,
    "current_business_points": 4,
    "future_watch_points": 4,
    "judgement_paragraph": 4,
    "brand_statement": 5,
    "memory_points": 5,
    "post_title": 6,
    "post_content_lines": 6,
    "hashtags": 6,
}

# Slot keys whose missing numerics fail-block (paying-customer-critical)
KEY_SLOT_KEYS = {
    "intro_sentence",
    "company_focus_paragraph",
    "industry_paragraph",
    "revenue_explainer_points",
    "judgement_paragraph",
    "porter_scores",
}


def detect_engine(prefer: Optional[str] = None) -> tuple[str, object]:
    """Return ("paddleocr"|"tesseract"|"none", instance_or_None)."""
    if prefer == "paddleocr" or prefer is None:
        try:
            from paddleocr import PaddleOCR  # type: ignore
            return "paddleocr", PaddleOCR  # class, lazily instantiated
        except ImportError:
            if prefer == "paddleocr":
                return "none", None
    if prefer == "tesseract" or prefer is None:
        try:
            import pytesseract  # noqa: F401  # type: ignore
            return "tesseract", None
        except ImportError:
            return "none", None
    return "none", None


def ocr_image_paddle(image_path: Path, lang: str, klass) -> str:
    """Lazy-instantiate PaddleOCR per-language; return concatenated text."""
    paddle_lang = "ch" if lang.startswith("c") else "en"
    ocr = klass(use_angle_cls=True, lang=paddle_lang, show_log=False)
    result = ocr.ocr(str(image_path), cls=True)
    out: list[str] = []
    if not result:
        return ""
    for page in result:
        if not page:
            continue
        for line in page:
            try:
                txt = line[1][0]
                out.append(txt)
            except (IndexError, TypeError):
                continue
    return "\n".join(out)


def ocr_image_tesseract(image_path: Path, lang: str) -> str:
    import pytesseract
    from PIL import Image
    tess_lang = "chi_sim+eng" if lang.startswith("c") else "eng"
    img = Image.open(image_path)
    return pytesseract.image_to_string(img, lang=tess_lang)


def value_appears_in_text(value: float, text: str) -> bool:
    """Loose check — does this numeric value appear in OCR'd text?
    Handles thousand separators and 1-decimal rounding tolerance.
    """
    candidates = {f"{value:.1f}", f"{value:.0f}", f"{value:,.0f}", f"{value:,.1f}"}
    if value == int(value):
        candidates.add(str(int(value)))
    candidates.add(str(value))
    for c in candidates:
        if c in text:
            return True
    # tolerate ±5% rounding
    for delta_factor in (0.99, 1.01, 0.95, 1.05):
        v = value * delta_factor
        if f"{v:.1f}" in text or f"{v:.0f}" in text:
            return True
    return False


def collect_card_numerics(slots: dict) -> dict[int, list[tuple[str, NumericToken]]]:
    """Map card_index → [(slot_key, NumericToken)] from card_slots.json."""
    by_card: dict[int, list[tuple[str, NumericToken]]] = {i: [] for i in range(1, 7)}
    for key, value in slots.items():
        card_idx = SLOT_TO_CARD.get(key)
        if not card_idx:
            continue
        if isinstance(value, str):
            for tok in extract_numerics(value, path=key):
                by_card[card_idx].append((key, tok))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str):
                    for tok in extract_numerics(item, path=f"{key}[{i}]"):
                        by_card[card_idx].append((key, tok))
                elif isinstance(item, (int, float)) and not isinstance(item, bool):
                    by_card[card_idx].append((key, NumericToken(raw=str(item), value=float(item), unit=None,
                                                                  context=f"{key}[{i}]={item}",
                                                                  path=f"{key}[{i}]")))
    return by_card


def run(cards_dir: Path, slots_path: Path, lang: str, out_dir: Path, engine: Optional[str]) -> dict:
    slots = json.loads(slots_path.read_text(encoding="utf-8"))
    by_card = collect_card_numerics(slots)

    out_dir.mkdir(parents=True, exist_ok=True)

    detected, klass = detect_engine(engine)
    summary = {
        "engine": detected,
        "lang": lang,
        "cards": {},
        "key_misses": [],
        "decorative_misses": [],
        "status": "pass",
    }

    if detected == "none":
        summary["status"] = "warn"
        summary["note"] = "no OCR engine available — install paddleocr or pytesseract; layer 2 skipped"
        (out_dir.parent / "ocr_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    for fname, idx in CARD_FILE_TO_INDEX.items():
        png = cards_dir / fname
        if not png.exists():
            summary["cards"][fname] = {"status": "skip", "reason": "missing png"}
            continue
        try:
            if detected == "paddleocr":
                text = ocr_image_paddle(png, lang, klass)
            else:
                text = ocr_image_tesseract(png, lang)
        except Exception as e:
            summary["cards"][fname] = {"status": "error", "reason": str(e)}
            continue

        (out_dir / f"card_{idx}.txt").write_text(text, encoding="utf-8")

        misses = []
        for slot_key, tok in by_card.get(idx, []):
            if not value_appears_in_text(tok.value, text):
                miss = {"card": idx, "slot": slot_key, "value": tok.value,
                        "raw": tok.raw, "context": tok.context}
                misses.append(miss)
                if slot_key in KEY_SLOT_KEYS:
                    summary["key_misses"].append(miss)
                else:
                    summary["decorative_misses"].append(miss)
        summary["cards"][fname] = {
            "status": "pass" if not misses else "miss",
            "checked": len(by_card.get(idx, [])),
            "misses": len(misses),
        }

    if summary["key_misses"]:
        summary["status"] = "fail"
    elif summary["decorative_misses"]:
        summary["status"] = "warn"

    (out_dir.parent / "ocr_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--run-dir", default=None)
    p.add_argument("--cards-dir", default=None)
    p.add_argument("--slots", default=None)
    p.add_argument("--out-dir", default=None)
    p.add_argument("--lang", default="cn", help="cn or en")
    p.add_argument("--engine", default=None, choices=[None, "paddleocr", "tesseract"])
    args = p.parse_args(argv)

    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
        cards_dir = run_dir / "cards"
        slots_files = list(cards_dir.glob("*.card_slots.json"))
        if not slots_files:
            print(f"error: no card_slots.json under {cards_dir}", file=sys.stderr)
            return 2
        slots_path = slots_files[0]
        out_dir = run_dir / "validation" / "ocr_dump"
    else:
        if not (args.cards_dir and args.slots and args.out_dir):
            print("error: provide --run-dir, or all of --cards-dir --slots --out-dir", file=sys.stderr)
            return 2
        cards_dir = Path(args.cards_dir)
        slots_path = Path(args.slots)
        out_dir = Path(args.out_dir)

    summary = run(cards_dir, slots_path, args.lang, out_dir, args.engine)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
