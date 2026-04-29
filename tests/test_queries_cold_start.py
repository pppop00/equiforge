"""db/queries.py — cold-start safety: every public read function returns [] / None on missing data."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.db import migrate, queries


@pytest.fixture
def fresh_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "kb.sqlite"
    migrate.apply_migrations(db)
    monkeypatch.setattr(queries, "DEFAULT_DB", db)
    return db


def test_no_db_means_empty_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    nonexistent = tmp_path / "nope.sqlite"
    monkeypatch.setattr(queries, "DEFAULT_DB", nonexistent)
    assert queries.get_prior_financials("AAPL") == []
    assert queries.get_peer_companies("AAPL", "Tech", "US") == []
    assert queries.get_peer_porter_matrix("Tech") == {}
    assert queries.get_macro_snapshot("US", "FY2026Q2") is None
    assert queries.search_signals("anything") == []
    assert queries.search_disclosure_quirks("Tech") == []
    assert queries.search_narratives("anything") == []
    assert queries.get_run_history("AAPL") == []
    assert queries.get_peer_revenue_growth("Tech", "FY2026") == []
    assert queries.get_sector_macro_consistency("Tech", "FY2026Q2") == []


def test_empty_db_means_empty_results(fresh_db: Path) -> None:
    assert queries.get_prior_financials("AAPL") == []
    assert queries.get_peer_porter_matrix("Tech") == {}
    assert queries.get_macro_snapshot("US", "FY2026Q2") is None
    assert queries.get_run_history("AAPL") == []
    assert queries.search_narratives("anything") == []
