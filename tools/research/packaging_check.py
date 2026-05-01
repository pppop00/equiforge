"""Static packaging check (P6 helper).

Verifies that all required research/ artifacts exist in the run dir and selects the
ER packaging profile from skills_repo/er/workflow_meta.json based on which artifacts
are present (sec_edgar_bundle.json → secapi=yes; qc_audit_trail.json → qc=full).
Also runs the locked-template HTML gate to prevent simplified hand-written report
pages from advancing into the card pipeline.

This is a static, deterministic check; the actual ER report_validator agent does
the structural HTML audit afterwards.

Usage:
    python tools/research/packaging_check.py --run-dir <path>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_skill_root  # noqa: E402
from validate_report_html import validate_html_report  # noqa: E402

PROFILES = {
    ("full", "yes"): "strict_18_full_qc_secapi",
    ("full", "no"): "strict_17_full_qc_no_secapi",
    ("fast", "yes"): "strict_13_fast_no_qc_secapi",
    ("fast", "no"): "strict_12_fast_no_qc_no_secapi",
}


def determine_profile(research_dir: Path) -> dict:
    qc_full = (research_dir / "qc_audit_trail.json").exists()
    sec_api = (research_dir / "sec_edgar_bundle.json").exists()
    profile = PROFILES[("full" if qc_full else "fast", "yes" if sec_api else "no")]

    required = {
        "financial_data.json",
        "macro_factors.json",
        "news_intel.json",
        "edge_insights.json",
        "financial_analysis.json",
        "prediction_waterfall.json",
        "porter_analysis.json",
        "final_report_data_validation.json",
    }
    if qc_full:
        required.update({
            "qc_macro_peer_a.json",
            "qc_macro_peer_b.json",
            "qc_porter_peer_a.json",
            "qc_porter_peer_b.json",
            "qc_audit_trail.json",
        })
    if sec_api:
        required.add("sec_edgar_bundle.json")

    html = sorted(p for p in research_dir.glob("*_Research_*.html") if not p.name.startswith("_locked_"))
    missing = sorted(f for f in required if not (research_dir / f).exists())
    if not html:
        missing.append("<Company>_Research_{CN|EN}.html")

    html_gate = None
    if len(html) == 1:
        lang = "cn" if html[0].name.endswith("_CN.html") else "en"
        skeleton_candidates = [
            research_dir / f"_locked_{lang}_skeleton.html",
            research_dir / "_locked_skeleton.html",
        ]
        skeleton = next((p for p in skeleton_candidates if p.exists()), None)
        html_gate = validate_html_report(html[0], skeleton)
        if html_gate["status"] == "critical":
            missing.append("locked_template_html_gate")
    elif len(html) > 1:
        missing.append("exactly_one_report_html")

    return {
        "profile": profile,
        "qc_mode": "full" if qc_full else "fast",
        "sec_api_mode": "yes" if sec_api else "no",
        "required_count": len(required) + 1,
        "missing": missing,
        "html_files": [p.name for p in html],
        "html_template_gate": html_gate,
        "status": "pass" if not missing else "critical",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--out", default=None, help="Write JSON to this path (default: <run-dir>/research/structure_conformance.json)")
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    research_dir = run_dir / "research"
    if not research_dir.exists():
        print(f"error: {research_dir} does not exist", file=sys.stderr)
        return 2

    result = determine_profile(research_dir)
    out_path = Path(args.out).resolve() if args.out else research_dir / "structure_conformance.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
