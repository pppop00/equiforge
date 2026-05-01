"""Validate that P5 produced a locked-template ER HTML report, not a simplified page.

This is a deterministic P5/P6 gate. It does not judge prose quality; it catches
the high-cost failure mode where the host model writes a short custom HTML page
instead of extracting the locked report skeleton and replacing placeholders.

Usage:
    python tools/research/validate_report_html.py --run-dir <path> --lang cn
    python tools/research/validate_report_html.py --html <report.html> --skeleton <_locked_cn_skeleton.html>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


REQUIRED_SECTION_IDS = (
    "section-summary",
    "section-financials",
    "section-prediction",
    "section-sankey",
    "section-porter",
    "section-appendix",
)

REQUIRED_MARKERS = (
    "CANONICAL CSS",
    "LOCKED JAVASCRIPT",
    "DATA VARIABLES",
    "drawWaterfall",
    "drawSankey",
    "drawRadar",
    "sankeyActualData",
    "sankeyForecastData",
    "porterScores",
    "waterfallData",
)

PLACEHOLDER_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")


def _find_single_report(research_dir: Path) -> Path | None:
    candidates = sorted(
        p for p in research_dir.glob("*_Research_*.html")
        if not p.name.startswith("_locked_")
    )
    if len(candidates) != 1:
        return None
    return candidates[0]


def _find_skeleton(research_dir: Path, lang: str) -> Path | None:
    candidates = [
        research_dir / f"_locked_{lang}_skeleton.html",
        research_dir / "_locked_skeleton.html",
        research_dir / "_locked_cn_skeleton.html" if lang == "zh" else research_dir / "_locked_en_skeleton.html",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _count(soup: BeautifulSoup, selector: str) -> int:
    return len(soup.select(selector))


def validate_html_report(html_path: Path, skeleton_path: Path | None = None) -> dict[str, Any]:
    html_path = html_path.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not html_path.exists():
        return {"status": "critical", "errors": [f"html file not found: {html_path}"], "warnings": []}

    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    skeleton_bytes = None
    if skeleton_path:
        skeleton_path = skeleton_path.resolve()
        if not skeleton_path.exists():
            errors.append(f"locked skeleton not found: {skeleton_path}")
        else:
            skeleton_bytes = len(skeleton_path.read_bytes())
            # The locked CN skeleton is ~38KB. A complete filled report may change
            # byte count, but a bespoke simplified page is usually far smaller.
            min_bytes = int(skeleton_bytes * 0.70)
            actual_bytes = len(html.encode("utf-8"))
            if actual_bytes < min_bytes:
                errors.append(
                    f"html is too small for locked template lineage: {actual_bytes} bytes < {min_bytes} bytes"
                )

    placeholders = sorted(set(PLACEHOLDER_RE.findall(html)))
    if placeholders:
        errors.append(f"unreplaced locked-template placeholders remain: {', '.join(placeholders[:12])}")

    for marker in REQUIRED_MARKERS:
        if marker not in html:
            errors.append(f"missing locked-template marker: {marker}")

    for section_id in REQUIRED_SECTION_IDS:
        if not soup.select_one(f"#{section_id}"):
            errors.append(f"missing required report section: #{section_id}")

    structural_counts = {
        "summary_para": _count(soup, "#section-summary .summary-para"),
        "kpi_card": _count(soup, "#section-financials .kpi-card"),
        "trend_card": _count(soup, "#section-financials .trend-card"),
        "porter_panel": _count(soup, '[id^="porter-panel-"]'),
        "sankey_svg": _count(soup, "#chart-sankey-actual") + _count(soup, "#chart-sankey-forecast"),
        "radar_canvas": _count(soup, 'canvas[id^="chart-radar-"]'),
    }
    expected = {
        "summary_para": 4,
        "kpi_card": 4,
        "trend_card": 5,
        "porter_panel": 3,
        "sankey_svg": 2,
        "radar_canvas": 3,
    }
    for key, need in expected.items():
        got = structural_counts[key]
        if got < need:
            errors.append(f"locked report structure incomplete: {key} count {got} < {need}")

    script_text = "\n".join(node.get_text("\n") for node in soup.find_all("script"))
    for var_name in ("waterfallData", "sankeyActualData", "sankeyForecastData", "porterScores"):
        if not re.search(rf"\bconst\s+{re.escape(var_name)}\s*=", script_text):
            errors.append(f"missing JS data variable: {var_name}")

    line_count = len(html.splitlines())
    if line_count < 500:
        errors.append(f"html line count is too low for locked report template: {line_count} < 500")

    return {
        "status": "critical" if errors else ("warn" if warnings else "pass"),
        "html_file": str(html_path),
        "skeleton_file": str(skeleton_path) if skeleton_path else None,
        "line_count": line_count,
        "byte_count": len(html.encode("utf-8")),
        "skeleton_byte_count": skeleton_bytes,
        "structural_counts": structural_counts,
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--run-dir", default=None)
    p.add_argument("--lang", default="cn", choices=["cn", "en", "zh"])
    p.add_argument("--html", default=None)
    p.add_argument("--skeleton", default=None)
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    if args.run_dir:
        research_dir = Path(args.run_dir).resolve() / "research"
        html_path = _find_single_report(research_dir)
        if html_path is None:
            result = {
                "status": "critical",
                "errors": [f"expected exactly one non-locked *_Research_*.html under {research_dir}"],
                "warnings": [],
            }
        else:
            skeleton = Path(args.skeleton).resolve() if args.skeleton else _find_skeleton(research_dir, args.lang)
            result = validate_html_report(html_path, skeleton)
    else:
        if not args.html:
            print("error: provide --run-dir or --html", file=sys.stderr)
            return 2
        result = validate_html_report(
            Path(args.html),
            Path(args.skeleton).resolve() if args.skeleton else None,
        )

    out_path = Path(args.out).resolve() if args.out else None
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "critical" else 1


if __name__ == "__main__":
    raise SystemExit(main())
