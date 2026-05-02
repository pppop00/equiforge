"""P12 layer 4 — cross-check this run vs DB history + peers + macro snapshot.

Cold-start safe (returns status='no_priors'). Never fail-blocks; emits warns only.

Three checks:
- self_history_yoy: compare reported YoY against DB's prior-period revenue.
- peer_porter_divergence: focal vs peer median per (perspective, force).
- macro_drift: same (geography, period) factors collected by other companies.

Usage:
    python tools/audit/db_cross_validate.py --run-dir <path>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "db"))
import queries  # type: ignore[import-not-found]

PORTER_FORCES = ("supplier", "buyer", "entrant", "substitute", "rivalry")


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return None
    if n % 2 == 1:
        return xs[n // 2]
    return (xs[n // 2 - 1] + xs[n // 2]) / 2


def load_research(run_dir: Path) -> dict:
    out = {}
    for name in ("financial_data", "financial_analysis", "macro_factors", "porter_analysis"):
        p = run_dir / "research" / f"{name}.json"
        out[name] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return out


def check_self_history(ticker: str, fiscal_period: str, fa: dict, fd: dict, run_id: str | None = None) -> dict:
    priors = [
        p for p in queries.get_prior_financials(ticker, n=4)
        if not run_id or p.get("source_run_id") != run_id
    ]
    if not priors:
        return {"id": "self_history_yoy", "severity": "info", "result": "no_priors"}

    reported_yoy = fd.get("income_statement", {}).get("yoy_revenue_pct") or fa.get("growth", {}).get("yoy_revenue_pct")
    if reported_yoy is None:
        return {"id": "self_history_yoy", "severity": "info", "result": "no_yoy_reported"}

    current_revenue = fd.get("income_statement", {}).get("current_year", {}).get("revenue")
    if current_revenue is None:
        return {"id": "self_history_yoy", "severity": "info", "result": "no_current_revenue"}

    prior = priors[0]
    prior_revenue = prior.get("revenue")
    if not prior_revenue:
        return {"id": "self_history_yoy", "severity": "info", "result": "prior_revenue_missing"}

    recomputed = (current_revenue / prior_revenue - 1.0) * 100.0
    delta = abs(recomputed - reported_yoy)
    severity = "warn" if delta > 5.0 else "info"
    return {
        "id": "self_history_yoy",
        "severity": severity,
        "result": "ok" if severity == "info" else "mismatch",
        "reported_yoy_pct": reported_yoy,
        "recomputed_yoy_pct": recomputed,
        "delta_pp": delta,
        "prior_run_id": prior.get("source_run_id"),
        "prior_period_end": prior.get("period_end_date"),
    }


def check_peer_porter(ticker: str, sector: str | None, pa: dict) -> dict:
    if not sector:
        return {"id": "peer_porter_divergence", "severity": "info", "result": "no_sector"}
    matrix = queries.get_peer_porter_matrix(sector=sector)
    matrix.pop(ticker, None)
    if len(matrix) < 2:
        return {"id": "peer_porter_divergence", "severity": "info", "result": "insufficient_peers", "peer_count": len(matrix)}

    company = pa.get("company_perspective") or {}
    scores = company.get("scores")
    if not isinstance(scores, list) or len(scores) < 5:
        return {"id": "peer_porter_divergence", "severity": "info", "result": "no_focal_scores"}

    focal = dict(zip(PORTER_FORCES, scores[:5]))
    flags = []
    for force, focal_score in focal.items():
        peer_scores = [v.get(force) for v in matrix.values() if v.get(force) is not None]
        if len(peer_scores) < 2:
            continue
        med = median(peer_scores)
        if med is None:
            continue
        agreers = sum(1 for s in peer_scores if abs(s - focal_score) <= 0.5)
        if abs(focal_score - med) >= 2 and agreers < 2:
            flags.append({
                "force": force,
                "focal": focal_score,
                "peer_median": med,
                "peers": list(matrix.keys()),
                "agreers": agreers,
            })
    return {
        "id": "peer_porter_divergence",
        "severity": "warn" if flags else "info",
        "result": "divergence" if flags else "ok",
        "flags": flags,
        "peer_count": len(matrix),
    }


def check_macro_drift(geography: str | None, period: str | None, mf: dict) -> dict:
    if not (geography and period):
        return {"id": "macro_factor_drift", "severity": "info", "result": "no_geography_or_period"}
    snapshot = queries.get_macro_snapshot(geography, period, max_age_days=365)
    if not snapshot:
        return {"id": "macro_factor_drift", "severity": "info", "result": "no_priors"}

    factors_by_slot = {}
    for f in mf.get("factors") or []:
        slot = f.get("factor_slot")
        if slot:
            factors_by_slot[slot] = f
    if not factors_by_slot:
        return {"id": "macro_factor_drift", "severity": "info", "result": "no_focal_factors"}

    flags = []
    for slot, prior in snapshot.get("factors", {}).items():
        focal = factors_by_slot.get(slot)
        if not focal:
            continue
        adj_diff = abs((focal.get("adjustment_pct") or 0) - (prior.get("adjustment_pct") or 0))
        beta_diff = abs((focal.get("beta") or 0) - (prior.get("beta") or 0))
        if adj_diff > 0.5 or beta_diff > 0.2:
            flags.append({
                "factor_slot": slot,
                "this_adjustment_pct": focal.get("adjustment_pct"),
                "prior_adjustment_pct": prior.get("adjustment_pct"),
                "this_beta": focal.get("beta"),
                "prior_beta": prior.get("beta"),
                "adjust_drift_pp": adj_diff,
                "beta_drift": beta_diff,
            })
    return {
        "id": "macro_factor_drift",
        "severity": "warn" if flags else "info",
        "result": "drift" if flags else "ok",
        "flags": flags,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--ticker", default=None)
    p.add_argument("--fiscal-period", default=None)
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    meta = json.loads((run_dir / "meta" / "run.json").read_text(encoding="utf-8"))
    research = load_research(run_dir)

    ticker = args.ticker or meta.get("ticker")
    fiscal_period = args.fiscal_period or research["financial_data"].get("fiscal_period") or meta.get("fiscal_period")
    sector = research["financial_data"].get("sector") or meta.get("sector")
    geography = research["macro_factors"].get("primary_operating_geography") or meta.get("primary_geography")

    checks = [
        check_self_history(ticker, fiscal_period, research["financial_analysis"], research["financial_data"], meta.get("run_id")),
        check_peer_porter(ticker, sector, research["porter_analysis"]),
        check_macro_drift(geography, fiscal_period, research["macro_factors"]),
    ]

    overall_status = "pass"
    if all(c.get("severity") == "info" and c.get("result") in {"no_priors", "insufficient_peers", "no_geography_or_period", "no_sector"} for c in checks):
        overall_status = "no_priors"
    elif any(c.get("severity") == "warn" for c in checks):
        overall_status = "warn"

    envelope = {
        "schema_version": 1,
        "run_id": meta.get("run_id"),
        "ticker": ticker,
        "fiscal_period": fiscal_period,
        "status": overall_status,
        "checks": checks,
    }
    out = Path(args.out) if args.out else run_dir / "validation" / "db_cross.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(envelope, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
