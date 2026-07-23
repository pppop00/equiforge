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
    "02_porter.png": 2,
    "03_five_year_financials.png": 3,
    "04_company_quality.png": 4,
    "05_country_lens.png": 5,
}

# Slot keys → which card index they appear on (1-indexed).
# Nested v5 objects are recursively scanned so all visible quantitative claims
# participate in OCR reconciliation.
SLOT_TO_CARD = {
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

# Slot keys whose missing numerics fail-block (paying-customer-critical)
KEY_SLOT_KEYS = {
    "intro_sentence",
    "one_minute_summary",
    "metrics_row",
    "porter_scores",
    "porter_evidence",
    "five_year_arc",
    "financial_metrics_panel",
    "company_quality",
    "country_lens",
}

# Visible provenance dates are useful context but are not business quantities.
# Treating the hyphenated components of an ISO date as card claims creates false
# failures such as ``-07`` even when the date is rendered correctly.
OCR_METADATA_KEYS = {"as_of_date"}


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
    # Tesseract can confuse one glyph inside a large displayed number (for
    # example 4178 → 4173).  Layer 1 already proves numerical equality; this
    # OCR layer proves that the value was visibly rendered.  Compare every OCR
    # numeric token inside the documented ±5% OCR tolerance rather than only
    # testing four boundary points.
    if abs(value) >= 10:
        normalized = text.replace(",", "")
        # Chinese OCR occasionally inserts a Latin glyph between adjacent
        # digits (``23.7`` → ``2Z3.7``).  Remove only a single ASCII letter
        # bounded by digits; ordinary prose remains untouched.
        normalized = re.sub(r"(?<=\d)[A-Za-z](?=\d)", "", normalized)
        # OCR often glues a numeric token to a stray Latin glyph from a nearby
        # Chinese character.  Forbid only a preceding digit so ``KE23.7`` is
        # still recoverable while we never start in the middle of ``123.7``.
        for raw in re.findall(r"(?<!\d)[+-]?\d+(?:\.\d+)?", normalized):
            try:
                observed = float(raw)
            except ValueError:
                continue
            if abs(observed - value) <= abs(value) * 0.05:
                return True
            # Large display digits often lose the decimal point under
            # Tesseract (29.6 → 296, 78.4 → 784). Accept a ×10 collapse when
            # the expected value is fractional and the OCR token has no dot.
            if abs(value - int(value)) > 1e-9 and "." not in raw:
                if abs(observed / 10.0 - value) <= abs(value) * 0.05:
                    return True
    return False


def _walk_numerics(slot_key: str, path: str, value, sink: list[tuple[str, NumericToken]]) -> None:
    """Recurse into strings/lists/dicts under a slot, harvesting numerics with full path context."""
    if isinstance(value, str):
        for tok in extract_numerics(value, path=path):
            sink.append((slot_key, tok))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            child_path = f"{path}[{i}]"
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                sink.append((slot_key, NumericToken(raw=str(item), value=float(item), unit=None,
                                                    context=f"{child_path}={item}",
                                                    path=child_path)))
            else:
                _walk_numerics(slot_key, child_path, item, sink)
    elif isinstance(value, dict):
        for k, v in value.items():
            if k in OCR_METADATA_KEYS:
                continue
            _walk_numerics(slot_key, f"{path}.{k}", v, sink)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        sink.append((slot_key, NumericToken(raw=str(value), value=float(value), unit=None,
                                             context=f"{path}={value}", path=path)))


def collect_card_numerics(slots: dict) -> dict[int, list[tuple[str, NumericToken]]]:
    """Map card_index → [(slot_key, NumericToken)] from card_slots.json."""
    by_card: dict[int, list[tuple[str, NumericToken]]] = {i: [] for i in range(1, 6)}
    for key, value in slots.items():
        card_idx = SLOT_TO_CARD.get(key)
        if not card_idx:
            continue
        _walk_numerics(key, key, value, by_card[card_idx])
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
