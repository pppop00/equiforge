"""Cross-company analytical reports from db/equity_kb.sqlite.

MVP: emits JSON only; HTML rendering is future work. The four report types are:

- porter_heatmap        — Force × peer 5×N grid (1-5)
- macro_consistency     — 6 factors × N quarters per geography
- peer_growth_attribution — baseline + macro + company waterfalls side-by-side
- signal_taxonomy       — signal_type histogram per sector

Usage:
    python tools/db/sector_report.py --type porter_heatmap --sector "Information Technology" --period FY2026Q2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import queries  # type: ignore[import-not-found]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SECTOR_REPORTS_DIR = PROJECT_ROOT / "db" / "sector_reports"


def slugify(s: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_") or "x"


def porter_heatmap(sector: str, period: str | None) -> dict:
    matrix = queries.get_peer_porter_matrix(sector=sector)
    return {
        "type": "porter_heatmap",
        "sector": sector,
        "period": period,
        "perspective": "company",
        "matrix": matrix,
        "peer_count": len(matrix),
    }


def macro_consistency(sector: str, period: str) -> dict:
    rows = queries.get_sector_macro_consistency(sector=sector, period=period)
    return {
        "type": "macro_consistency",
        "sector": sector,
        "period": period,
        "rows": rows,
        "row_count": len(rows),
    }


def peer_growth_attribution(sector: str, period: str) -> dict:
    rows = queries.get_peer_revenue_growth(sector=sector, fiscal_period=period)
    return {
        "type": "peer_growth_attribution",
        "sector": sector,
        "period": period,
        "rows": rows,
        "peer_count": len(rows),
    }


def signal_taxonomy(sector: str) -> dict:
    try:
        conn = queries.open_conn()
    except FileNotFoundError:
        return {"type": "signal_taxonomy", "sector": sector, "rows": [], "row_count": 0}
    try:
        cur = conn.execute(
            """SELECT signal_type, COUNT(*) AS n FROM intelligence_signals
                WHERE sector = ?
                GROUP BY signal_type ORDER BY n DESC""",
            (sector,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        return {
            "type": "signal_taxonomy",
            "sector": sector,
            "rows": rows,
            "row_count": len(rows),
        }
    finally:
        conn.close()


REPORTS = {
    "porter_heatmap": porter_heatmap,
    "macro_consistency": macro_consistency,
    "peer_growth_attribution": peer_growth_attribution,
    "signal_taxonomy": signal_taxonomy,
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--type", required=True, choices=list(REPORTS.keys()))
    p.add_argument("--sector", required=True)
    p.add_argument("--period", default=None, help="fiscal_period (required for macro_consistency / peer_growth_attribution)")
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    if args.type in {"macro_consistency", "peer_growth_attribution"} and not args.period:
        print(f"error: --period is required for {args.type}", file=sys.stderr)
        return 2

    fn = REPORTS[args.type]
    if args.type == "signal_taxonomy":
        result = fn(args.sector)  # type: ignore[arg-type]
    else:
        result = fn(args.sector, args.period)  # type: ignore[arg-type]

    out_dir = Path(args.out) if args.out else SECTOR_REPORTS_DIR / f"{args.type}_{slugify(args.sector)}_{args.period or 'all'}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / f"{args.type}.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out_json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
