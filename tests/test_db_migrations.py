"""tools/db/migrate.py — applies numbered SQL migrations idempotently."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.db import migrate


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_migrate_creates_schema_meta_and_user_version(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    result = migrate.apply_migrations(db)
    assert result["current_version"] >= 2
    assert 1 in result["applied"]
    assert 2 in result["applied"]

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT schema_version FROM schema_meta ORDER BY schema_version").fetchall()
        assert rows[0][0] == 1
        assert rows[-1][0] == result["current_version"]
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


def test_migrate_upgrades_existing_v1_card_slots(tmp_path: Path) -> None:
    db = tmp_path / "v1.sqlite"
    conn = sqlite3.connect(db)
    try:
        schema_001 = (PROJECT_ROOT / "db" / "schema" / "001_init.sql").read_text(
            encoding="utf-8"
        )
        conn.executescript(schema_001)
        conn.execute("PRAGMA user_version = 1")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 1
        before = {
            row[1] for row in conn.execute("PRAGMA table_info(card_slots)").fetchall()
        }
        assert "cfa_lens_formula" not in before
        assert "cfa_lens_calculation" not in before
    finally:
        conn.close()

    result = migrate.apply_migrations(db)
    assert result["previous_version"] == 1
    assert result["applied"] == [2]
    assert result["current_version"] >= 2

    conn = sqlite3.connect(db)
    try:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(card_slots)").fetchall()
        }
        assert "cfa_lens_formula" in columns
        assert "cfa_lens_calculation" in columns
    finally:
        conn.close()


def test_migrate_marks_card4_v3_when_columns_already_exist(tmp_path: Path) -> None:
    db = tmp_path / "already_has_card4_v3.sqlite"
    conn = sqlite3.connect(db)
    try:
        schema_001 = (PROJECT_ROOT / "db" / "schema" / "001_init.sql").read_text(
            encoding="utf-8"
        )
        conn.executescript(schema_001)
        conn.execute("ALTER TABLE card_slots ADD COLUMN cfa_lens_formula TEXT")
        conn.execute("ALTER TABLE card_slots ADD COLUMN cfa_lens_calculation TEXT")
        conn.execute("PRAGMA user_version = 1")
    finally:
        conn.close()

    result = migrate.apply_migrations(db)
    assert result["previous_version"] == 1
    assert result["applied"] == [2]
    assert result["current_version"] >= 2

    conn = sqlite3.connect(db)
    try:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(card_slots)").fetchall()
        }
        assert "cfa_lens_formula" in columns
        assert "cfa_lens_calculation" in columns
    finally:
        conn.close()
