"""tools/db/sector_report.py — JSON + HTML output, including cold-start handling."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tools.db import migrate, sector_report


@pytest.fixture
def empty_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "kb.sqlite"
    migrate.apply_migrations(db)
    monkeypatch.setattr(sector_report.queries, "DEFAULT_DB", db)
    return db


@pytest.fixture
def seeded_db(empty_db: Path) -> Path:
    conn = sqlite3.connect(empty_db)
    try:
        for ticker, sector, geo in (
            ("AAPL", "Information Technology", "US"),
            ("MSFT", "Information Technology", "US"),
            ("NVDA", "Information Technology", "US"),
        ):
            conn.execute(
                "INSERT INTO companies (ticker, exchange, name_en, sector, primary_geography, last_run_date) VALUES (?, ?, ?, ?, ?, ?)",
                (ticker, "NASDAQ", ticker, sector, geo, "2026-04-28"),
            )
            conn.execute(
                "INSERT INTO runs (run_id, ticker, run_date, language, run_status) VALUES (?, ?, ?, ?, ?)",
                (f"r_{ticker}", ticker, "2026-04-28", "en", "complete"),
            )
        # 15 Porter rows per company × 3 companies = 45
        for ticker, scores in (
            ("AAPL", [3, 3, 2, 3, 4]),
            ("MSFT", [3, 2, 2, 3, 4]),
            ("NVDA", [4, 2, 3, 3, 5]),
        ):
            for force, score in zip(("supplier", "buyer", "entrant", "substitute", "rivalry"), scores):
                conn.execute(
                    """INSERT INTO porter_scores_period
                          (ticker, fiscal_period, perspective, force, score, source_run_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (ticker, "FY2026", "company", force, score, f"r_{ticker}"),
                )
        # signals
        for i in range(3):
            conn.execute(
                """INSERT INTO intelligence_signals
                      (sig_id, ticker, sector, signal_type, fact, observation_date, source_run_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (f"sig{i}", "AAPL", "Information Technology", "product_cycle",
                 f"signal {i}", "2026-04-28", "r_AAPL"),
            )
        conn.execute(
            """INSERT INTO intelligence_signals
                  (sig_id, ticker, sector, signal_type, fact, observation_date, source_run_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("sig_p", "MSFT", "Information Technology", "policy_regulation",
             "policy", "2026-04-28", "r_MSFT"),
        )
        conn.commit()
    finally:
        conn.close()
    return empty_db


def test_porter_heatmap_html_and_json(seeded_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "report"
    rc = sector_report.main([
        "--type", "porter_heatmap",
        "--sector", "Information Technology",
        "--period", "FY2026",
        "--out", str(out),
    ])
    assert rc == 0
    json_path = out / "porter_heatmap.json"
    html_path = out / "porter_heatmap.html"
    assert json_path.exists()
    assert html_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert set(payload["matrix"].keys()) == {"AAPL", "MSFT", "NVDA"}
    html = html_path.read_text(encoding="utf-8")
    assert "AAPL" in html and "MSFT" in html and "NVDA" in html
    assert "rivalry" in html


def test_signal_taxonomy(seeded_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "report"
    rc = sector_report.main([
        "--type", "signal_taxonomy",
        "--sector", "Information Technology",
        "--out", str(out),
    ])
    assert rc == 0
    payload = json.loads((out / "signal_taxonomy.json").read_text(encoding="utf-8"))
    types = {r["signal_type"]: r["n"] for r in payload["rows"]}
    assert types.get("product_cycle") == 3
    assert types.get("policy_regulation") == 1
    html = (out / "signal_taxonomy.html").read_text(encoding="utf-8")
    assert "product_cycle" in html


def test_macro_consistency_cold_start(empty_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "report"
    rc = sector_report.main([
        "--type", "macro_consistency",
        "--sector", "Information Technology",
        "--period", "FY2026Q2",
        "--out", str(out),
    ])
    assert rc == 0
    payload = json.loads((out / "macro_consistency.json").read_text(encoding="utf-8"))
    assert payload["row_count"] == 0
    html = (out / "macro_consistency.html").read_text(encoding="utf-8")
    # Cold-start renders a friendly empty message
    assert "No macro" in html or "empty" in html.lower()


def test_peer_growth_requires_period(seeded_db: Path, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    rc = sector_report.main([
        "--type", "peer_growth_attribution",
        "--sector", "Information Technology",
    ])
    assert rc == 2
    captured = capsys.readouterr()
    assert "--period is required" in captured.err
