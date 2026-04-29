"""tools/db/migrate.py — applies numbered SQL migrations idempotently."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.db import migrate


def test_migrate_creates_schema_meta_and_user_version(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    result = migrate.apply_migrations(db)
    assert result["current_version"] >= 1
    assert 1 in result["applied"]

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT schema_version FROM schema_meta ORDER BY schema_version").fetchall()
        assert rows[0][0] == 1
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == result["current_version"]
    finally:
        conn.close()


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    first = migrate.apply_migrations(db)
    second = migrate.apply_migrations(db)
    assert second["applied"] == []
    assert second["current_version"] == first["current_version"]


def test_migrate_creates_required_tables(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    migrate.apply_migrations(db)
    conn = sqlite3.connect(db)
    try:
        names = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
        ).fetchall()}
        for required in (
            "companies", "runs", "financials_period", "financials_period_history",
            "segments_period", "macro_factors_period", "porter_scores_period",
            "prediction_waterfall_period", "intelligence_signals", "edge_insights",
            "disclosure_quirks", "qc_events", "validation_findings", "card_slots",
            "fts_narratives", "schema_meta",
        ):
            assert required in names, f"missing table: {required}"
    finally:
        conn.close()


def test_dry_run_does_not_apply(tmp_path: Path) -> None:
    db = tmp_path / "dryrun.sqlite"
    result = migrate.apply_migrations(db, dry_run=True)
    assert result["applied"] == []
    assert 1 in result["pending"]
    # The DB file should exist but be empty (or not contain our tables)
    if db.exists():
        conn = sqlite3.connect(db)
        try:
            names = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            assert "schema_meta" not in names
        finally:
            conn.close()
