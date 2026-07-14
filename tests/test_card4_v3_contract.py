"""Historical CFA DB columns remain, but schema-v5 active paths exclude CFA."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_active_web_priority_uses_company_quality_and_country_lens() -> None:
    web = _load("web_v5", "tools/audit/web_third_check.py")
    assert "card_slots.company_quality.valuation" in web.PRIORITY_PATHS
    assert "card_slots.country_lens.dimensions" in web.PRIORITY_PATHS
    assert not any("cfa_lens" in path for path in web.PRIORITY_PATHS)


def test_voice_gate_uses_claim_level_v5_contract() -> None:
    source = (PROJECT_ROOT / "tools/photo/voice_gate.py").read_text(encoding="utf-8")
    assert "validate_card1_5_analytical_content" in source
    assert "--cfa-progress" not in source


def test_historical_cfa_columns_survive_migrations(tmp_path: Path) -> None:
    migrate = _load("migrate_v5_history", "tools/db/migrate.py")
    db = tmp_path / "history.sqlite"
    migrate.apply_migrations(db)
    conn = sqlite3.connect(db)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(card_slots)")}
    finally:
        conn.close()
    assert {"cfa_lens_formula", "cfa_lens_calculation"} <= columns
