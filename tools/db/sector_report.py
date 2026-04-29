"""Cross-company analytical reports from db/equity_kb.sqlite.

Each report writes BOTH a JSON (raw rows for re-ingestion) and a self-contained
HTML (no external deps; inline CSS) into db/sector_reports/{type}_{sector}_{period}/.

Report types:
- porter_heatmap          — Force × peer 5×N grid (1-5)
- macro_consistency       — 6 factors × N quarters per geography
- peer_growth_attribution — baseline / macro / company waterfalls side-by-side
- signal_taxonomy         — signal_type histogram per sector

Usage:
    python tools/db/sector_report.py --type porter_heatmap --sector "Information Technology" --period FY2026Q2
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import queries  # type: ignore[import-not-found]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SECTOR_REPORTS_DIR = PROJECT_ROOT / "db" / "sector_reports"

PORTER_FORCES = ("supplier", "buyer", "entrant", "substitute", "rivalry")


def slugify(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_") or "x"


# ─────────────────────────────────────────────────────────────────────
# Data builders
# ─────────────────────────────────────────────────────────────────────

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


def signal_taxonomy(sector: str, period: str | None = None) -> dict:
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


# ─────────────────────────────────────────────────────────────────────
# HTML rendering
# ─────────────────────────────────────────────────────────────────────

CSS = """
:root {
  --bg: #fbf6ef;
  --ink: #141a2c;
  --muted: #6b7280;
  --line: #e5e0d6;
  --accent-1: #d86b79;
  --accent-2: #d68852;
  --accent-3: #8fcf9f;
  --accent-4: #9fb9e2;
}
body { font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif;
       background: var(--bg); color: var(--ink); margin: 0; padding: 32px 48px; }
h1 { margin: 0 0 4px; font-size: 22px; }
.meta { color: var(--muted); margin-bottom: 24px; font-size: 13px; }
table { border-collapse: collapse; margin-top: 16px; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--line); }
th { font-weight: 600; background: rgba(20,26,44,0.04); }
.heatmap td { text-align: center; min-width: 56px; font-weight: 600; }
.s1 { background: #d6f1d6; }    /* low threat */
.s2 { background: #e8f3d6; }
.s3 { background: #fce8b8; }    /* mixed */
.s4 { background: #f4c0a3; }
.s5 { background: #ec8a8a; color: white; }    /* high threat */
.empty { color: var(--muted); font-style: italic; padding: 24px 0; }
.bar { display: inline-block; height: 12px; background: var(--accent-2); vertical-align: middle; }
.legend { margin-top: 16px; font-size: 12px; color: var(--muted); }
.legend span { display: inline-block; padding: 2px 8px; margin-right: 4px; border-radius: 3px; }
.value-pos { color: var(--accent-3); }
.value-neg { color: var(--accent-1); }
"""


def _h(s) -> str:
    return html.escape(str(s) if s is not None else "")


def _shell(title: str, body: str, meta_lines: list[str]) -> str:
    meta_html = "<br>".join(_h(m) for m in meta_lines)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>{_h(title)}</title>
<style>{CSS}</style>
</head><body>
<h1>{_h(title)}</h1>
<div class="meta">{meta_html}</div>
{body}
</body></html>
"""


def render_porter_heatmap(payload: dict) -> str:
    matrix = payload["matrix"] or {}
    if not matrix:
        body = '<p class="empty">No peers in DB for this sector. Run a few companies first.</p>'
    else:
        head = "<tr><th>Ticker</th>" + "".join(f"<th>{f}</th>" for f in PORTER_FORCES) + "</tr>"
        rows = []
        for ticker in sorted(matrix.keys()):
            cells = []
            for force in PORTER_FORCES:
                score = matrix[ticker].get(force)
                if score is None:
                    cells.append("<td>—</td>")
                else:
                    cells.append(f'<td class="s{int(score)}">{int(score)}</td>')
            rows.append(f"<tr><td><strong>{_h(ticker)}</strong></td>" + "".join(cells) + "</tr>")
        body = '<table class="heatmap">' + head + "".join(rows) + "</table>"
        body += '<p class="legend">Threat / pressure scale: '
        for s in range(1, 6):
            body += f'<span class="s{s}">{s}</span>'
        body += ' (1 = low threat / green · 5 = high threat / red)</p>'
    title = f'Porter Heatmap — {payload["sector"]}'
    meta = [f'Period: {payload.get("period") or "all"}',
            f'Perspective: {payload.get("perspective", "company")}',
            f'Peer count: {payload.get("peer_count", 0)}']
    return _shell(title, body, meta)


def render_macro_consistency(payload: dict) -> str:
    rows = payload["rows"] or []
    if not rows:
        body = '<p class="empty">No macro rows for this (sector, period). Run companies in this geography first.</p>'
    else:
        head = ("<tr><th>Geography</th><th>Period</th><th>Slot</th><th>Current</th>"
                "<th>Forecast</th><th>β</th><th>Adj %</th><th>Source</th></tr>")
        body_rows = []
        for r in rows:
            body_rows.append(
                "<tr>"
                f"<td>{_h(r.get('geography'))}</td>"
                f"<td>{_h(r.get('period'))}</td>"
                f"<td>{_h(r.get('factor_slot'))}</td>"
                f"<td>{_h(r.get('current_value'))}</td>"
                f"<td>{_h(r.get('forecast_value'))}</td>"
                f"<td>{_h(r.get('beta'))}</td>"
                f"<td>{_h(r.get('adjustment_pct'))}</td>"
                f"<td>{_h(r.get('source'))}</td>"
                "</tr>"
            )
        body = "<table>" + head + "".join(body_rows) + "</table>"
    title = f'Macro Consistency — {payload["sector"]}'
    meta = [f'Period: {payload.get("period")}', f'Rows: {payload.get("row_count", 0)}']
    return _shell(title, body, meta)


def render_peer_growth_attribution(payload: dict) -> str:
    rows = payload["rows"] or []
    if not rows:
        body = '<p class="empty">No peer revenue rows for this (sector, period).</p>'
    else:
        max_yoy = max(abs(r.get("yoy_revenue_pct") or 0) for r in rows) or 1
        body_rows = []
        for r in rows:
            yoy = r.get("yoy_revenue_pct") or 0
            width_px = int(abs(yoy) / max_yoy * 200)
            cls = "value-pos" if yoy >= 0 else "value-neg"
            body_rows.append(
                "<tr>"
                f"<td><strong>{_h(r.get('ticker'))}</strong></td>"
                f"<td>{_h(r.get('fiscal_period'))}</td>"
                f"<td>{_h(r.get('revenue'))}</td>"
                f'<td class="{cls}">{_h(round(yoy, 2))}%</td>'
                f'<td><span class="bar" style="width: {width_px}px"></span></td>'
                "</tr>"
            )
        body = ("<table>"
                "<tr><th>Ticker</th><th>Period</th><th>Revenue</th><th>YoY %</th><th></th></tr>"
                + "".join(body_rows) + "</table>")
    title = f'Peer Revenue Growth — {payload["sector"]}'
    meta = [f'Period: {payload.get("period")}', f'Peers: {payload.get("peer_count", 0)}']
    return _shell(title, body, meta)


def render_signal_taxonomy(payload: dict) -> str:
    rows = payload["rows"] or []
    if not rows:
        body = '<p class="empty">No intelligence signals for this sector.</p>'
    else:
        max_n = max(r.get("n", 0) for r in rows) or 1
        body_rows = []
        for r in rows:
            n = r.get("n", 0)
            width_px = int(n / max_n * 240)
            body_rows.append(
                "<tr>"
                f"<td>{_h(r.get('signal_type') or '(unspecified)')}</td>"
                f"<td>{_h(n)}</td>"
                f'<td><span class="bar" style="width: {width_px}px"></span></td>'
                "</tr>"
            )
        body = ("<table>"
                "<tr><th>Signal type</th><th>Count</th><th></th></tr>"
                + "".join(body_rows) + "</table>")
    title = f'Signal Taxonomy — {payload["sector"]}'
    meta = [f'Rows: {payload.get("row_count", 0)}']
    return _shell(title, body, meta)


RENDERERS = {
    "porter_heatmap": render_porter_heatmap,
    "macro_consistency": render_macro_consistency,
    "peer_growth_attribution": render_peer_growth_attribution,
    "signal_taxonomy": render_signal_taxonomy,
}


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--type", required=True, choices=list(REPORTS.keys()))
    p.add_argument("--sector", required=True)
    p.add_argument("--period", default=None)
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    if args.type in {"macro_consistency", "peer_growth_attribution"} and not args.period:
        print(f"error: --period is required for {args.type}", file=sys.stderr)
        return 2

    fn = REPORTS[args.type]
    if args.type == "signal_taxonomy":
        result = fn(args.sector, None)
    else:
        result = fn(args.sector, args.period)

    out_dir = (Path(args.out) if args.out else
               SECTOR_REPORTS_DIR / f"{args.type}_{slugify(args.sector)}_{args.period or 'all'}")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{args.type}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    html_path = out_dir / f"{args.type}.html"
    html_path.write_text(RENDERERS[args.type](result), encoding="utf-8")

    print(json.dumps({"json": str(json_path), "html": str(html_path),
                       "type": args.type, "sector": args.sector,
                       "period": args.period, "rows": result.get("row_count") or result.get("peer_count", 0)},
                      ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
