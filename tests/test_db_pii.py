"""Privacy regression: no row in any TEXT column may match an email regex after a fixture run."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from tools.db import index_run, migrate
from tools.io import run_dir as run_dir_mod

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _seed_run_dir(tmp_path: Path) -> Path:
    rd = run_dir_mod.init_run_dir("Apple", "2026-04-28", run_id="piitest1", output_root=tmp_path)

    # meta/run.json with sticky email — our orchestrator-level capture, not for DB
    (rd / "meta" / "run.json").write_text(json.dumps({
        "run_id": "piitest1",
        "ticker": "AAPL",
        "company": "Apple Inc.",
        "date": "2026-04-28",
        "started_at": "2026-04-28T00:00:00Z",
        "report_language": "en",
        "fiscal_period": "FY2026",
        "primary_geography": "US",
    }), encoding="utf-8")
    (rd / "meta" / "gates.json").write_text(json.dumps({
        "P0_lang": {"value": "en", "source": "user_response"},
        "P0_sec_email": {"value": "user@example.com",
                          "sec_user_agent": "EquityFusionSkill/1.0 (user@example.com)",
                          "source": "user_response"},
        "P0_palette": {"value": "macaron", "source": "user_response"},
    }), encoding="utf-8")

    # financial_data.json with a User-Agent leak inside data_source
    (rd / "research" / "financial_data.json").write_text(json.dumps({
        "ticker": "AAPL",
        "company": "Apple Inc.",
        "fiscal_period": "FY2026",
        "fiscal_year_end": "2026-09-30",
        "currency": "USD",
        "unit": "billion",
        "sector": "Information Technology",
        "primary_operating_geography": "US",
        "data_source": "SEC EDGAR via EquityResearchSkill/1.0 (real.user@example.com)",
        "data_confidence": "high",
        "income_statement": {
            "current_year": {
                "revenue": 391.0, "gross_profit": 169.0, "net_income": 96.0,
                "gross_margin": 43.2, "operating_margin": 31.5, "net_margin": 24.5,
            },
            "yoy_revenue_pct": 5.2,
            "yoy_net_income_pct": 9.0,
        },
        "balance_sheet": {"total_assets": 364.0, "total_debt": 96.0},
        "cash_flow": {"operating_cash_flow": 110.0, "capex": -10.5, "free_cash_flow": 99.5},
        "segment_data": [{"segment_name": "iPhone", "revenue": 200.0, "pct_of_total": 51.2}],
        "disclosure_quirks": [{"description": "Services revenue restated", "basis_change": "yes"}],
    }), encoding="utf-8")

    (rd / "research" / "macro_factors.json").write_text(json.dumps({
        "primary_operating_geography": "US",
        "factors": [
            {"name": "policy_rate", "factor_slot": "rate", "current_value": 5.0, "forecast_value": 4.5, "beta": 0.15, "phi": 0.5, "adjustment_pct": -0.3, "source": "Fed"},
            {"name": "gdp", "factor_slot": "gdp", "current_value": 2.1, "forecast_value": 2.3, "beta": 0.35, "phi": 0.5, "adjustment_pct": 0.1, "source": "BEA"},
            {"name": "cpi", "factor_slot": "inflation", "current_value": 3.0, "forecast_value": 2.8, "beta": 0.10, "phi": 0.5, "adjustment_pct": 0.0, "source": "BLS"},
            {"name": "fx", "factor_slot": "fx", "current_value": 1.0, "forecast_value": 1.0, "beta": 0.05, "phi": 0.5, "adjustment_pct": 0.0, "source": "FRED"},
            {"name": "oil", "factor_slot": "oil", "current_value": 80, "forecast_value": 75, "beta": 0.05, "phi": 0.5, "adjustment_pct": -0.05, "source": "EIA"},
            {"name": "consumer_confidence", "factor_slot": "consumer_confidence", "current_value": 100.0, "forecast_value": 102.0, "beta": 0.20, "phi": 0.5, "adjustment_pct": 0.05, "source": "Conf Board"},
        ],
        "macro_factor_commentary": "Cycle moderating.",
    }), encoding="utf-8")

    (rd / "research" / "financial_analysis.json").write_text(json.dumps({
        "investment_thesis_short": "Apple maintains durable platform economics.",
        "executive_summary": "Net margin expanded; FCF stable.",
        "metrics": [{"name": "ROIC", "value": 30.0}, {"name": "FCF margin", "value": 25.5}],
        "growth": {"yoy_revenue_pct": 5.2, "eps_growth_pct": 9.0},
    }), encoding="utf-8")

    (rd / "research" / "porter_analysis.json").write_text(json.dumps({
        "company_perspective": {"scores": [3, 3, 2, 3, 4], "narrative": "Strong moat in services."},
        "industry_perspective": {"scores": [3, 3, 3, 4, 4], "narrative": "Industry rivalry intense."},
        "forward_perspective": {"scores": [4, 4, 4, 4, 5], "narrative": "AI raises substitute pressure."},
    }), encoding="utf-8")

    (rd / "research" / "news_intel.json").write_text(json.dumps({
        "narrative_summary": "Quarter showed services strength.",
        "intelligence_signals": [
            {"id": "sig-001", "type": "product_cycle", "fact": "iPhone 17 ramp",
             "affected_metric": "revenue", "watch_metric": "iPhone units",
             "thesis_implication": "near-term tailwind"},
        ],
    }), encoding="utf-8")

    (rd / "research" / "edge_insights.json").write_text(json.dumps({
        "chosen_insight": {
            "headline": "Services TTM gross margin reached 76%",
            "insight_type": "non_consensus_read",
            "surface_read": "Services growing",
            "hidden_rule": "Mix shift from hardware",
            "investment_implication": "Multiple expansion",
            "confidence": "high",
        }
    }), encoding="utf-8")

    (rd / "research" / "prediction_waterfall.json").write_text(json.dumps({
        "baseline_growth_pct": 5.0,
        "macro_adjustments": [{"factor": "rate", "adjustment_pct": -0.3}],
        "company_specific_adjustment_pct": 0.5,
        "predicted_revenue_growth_pct": 5.2,
        "predicted_revenue": 411.4,
        "phi": 0.5,
        "confidence": "medium",
    }), encoding="utf-8")

    (rd / "research" / "qc_audit_trail.json").write_text(json.dumps({
        "macro": {"items": [{"id": "MA-001", "verdict": "retain_analyst", "rationale": "Fine"}]},
        "porter": {"items": [{"id": "PA-001", "perspective": "company", "force": "rivalry",
                                "verdict": "retain_analyst", "score_changed": False,
                                "score_before": 4, "score_after": 4, "weighted_score": 4.0,
                                "delta_vs_draft": 0.0}]},
    }), encoding="utf-8")

    (rd / "research" / "final_report_data_validation.json").write_text(json.dumps({
        "summary": {"status": "pass", "total_critical": 0, "total_warning": 1},
        "warning_items": [{"id": "W-001", "category": "rounding",
                            "description": "Sankey total off by 0.1%", "root_cause": "rounding"}],
    }), encoding="utf-8")

    return rd


def test_index_run_does_not_persist_email(tmp_path: Path) -> None:
    rd = _seed_run_dir(tmp_path)
    db_path = tmp_path / "kb.sqlite"
    migrate.apply_migrations(db_path)
    res = index_run.index_run(rd, db_path)
    assert not res.errors, f"index errored: {res.errors}"

    conn = sqlite3.connect(db_path)
    try:
        text_columns_per_table = []
        for (table,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'fts_%' AND name NOT LIKE '%_fts%' AND name NOT IN ('schema_meta')"
        ).fetchall():
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            text_cols = [c[1] for c in cols if (c[2] or "").upper() in {"TEXT", ""}]
            for col in text_cols:
                text_columns_per_table.append((table, col))

        offenders = []
        for table, col in text_columns_per_table:
            cur = conn.execute(f"SELECT rowid, {col} FROM {table} WHERE {col} LIKE '%@%'")
            for rowid, value in cur.fetchall():
                if value and EMAIL_RE.search(value):
                    offenders.append((table, col, rowid, value))
        assert not offenders, f"PII leak: {offenders}"
    finally:
        conn.close()


def test_index_run_writes_expected_tables(tmp_path: Path) -> None:
    rd = _seed_run_dir(tmp_path)
    db_path = tmp_path / "kb.sqlite"
    migrate.apply_migrations(db_path)
    res = index_run.index_run(rd, db_path)
    assert res.run_id is not None
    assert res.ticker == "AAPL"

    conn = sqlite3.connect(db_path)
    try:
        for table in ("companies", "runs", "financials_period", "macro_factors_period",
                      "porter_scores_period", "intelligence_signals", "edge_insights",
                      "disclosure_quirks", "qc_events"):
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert n >= 1, f"{table} empty (touched={res.tables_touched.get(table)})"
        assert conn.execute("SELECT COUNT(*) FROM porter_scores_period").fetchone()[0] == 15
        assert conn.execute("SELECT COUNT(*) FROM macro_factors_period").fetchone()[0] == 6
    finally:
        conn.close()
