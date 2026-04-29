"""Read-side query API for the orchestrator and audit tools.

All functions return [] / None on no data (cold-start safe). They never raise on
missing rows — only on actual SQL errors.

Default: filter on `runs.run_status = 'complete'` so partial runs don't poison
cross-validation. Pass include_partial=True to see everything for audit.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "db" / "equity_kb.sqlite"


def open_conn(db_path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(db_path) if db_path else DEFAULT_DB
    if not p.exists():
        raise FileNotFoundError(f"db not found: {p} (run tools/db/migrate.py first)")
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _rows(cursor) -> list[dict]:
    return [dict(r) for r in cursor.fetchall()]


# ─────────────────────────────────────────────────────────────────────
# Read API
# ─────────────────────────────────────────────────────────────────────

def get_prior_financials(ticker: str, n: int = 4, conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    own = conn is None
    if own:
        try:
            conn = open_conn()
        except FileNotFoundError:
            return []
    try:
        sql = """
            SELECT fp.*
              FROM financials_period fp
              JOIN runs r ON r.run_id = fp.source_run_id
             WHERE fp.ticker = ?
               AND r.run_status = 'complete'
             ORDER BY COALESCE(fp.period_end_date, fp.fiscal_period) DESC
             LIMIT ?
        """
        return _rows(conn.execute(sql, (ticker, n)))
    finally:
        if own:
            conn.close()


def get_peer_companies(
    ticker: Optional[str] = None,
    sector: Optional[str] = None,
    geography: Optional[str] = None,
    limit: int = 8,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict]:
    own = conn is None
    if own:
        try:
            conn = open_conn()
        except FileNotFoundError:
            return []
    try:
        clauses = []
        params: list = []
        if sector:
            clauses.append("sector = ?")
            params.append(sector)
        if geography:
            clauses.append("primary_geography = ?")
            params.append(geography)
        if ticker:
            clauses.append("ticker != ?")
            params.append(ticker)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM companies{where} ORDER BY last_run_date DESC LIMIT ?"
        params.append(limit)
        return _rows(conn.execute(sql, params))
    finally:
        if own:
            conn.close()


def get_peer_porter_matrix(
    sector: str,
    fiscal_period_window: int = 2,
    perspective: str = "company",
    conn: Optional[sqlite3.Connection] = None,
) -> dict[str, dict[str, int]]:
    """Return {ticker: {force: score}} for peers in this sector."""
    own = conn is None
    if own:
        try:
            conn = open_conn()
        except FileNotFoundError:
            return {}
    try:
        sql = """
            SELECT psp.ticker, psp.force, psp.score, psp.fiscal_period
              FROM porter_scores_period psp
              JOIN companies c ON c.ticker = psp.ticker
              JOIN runs r ON r.run_id = psp.source_run_id
             WHERE c.sector = ?
               AND psp.perspective = ?
               AND r.run_status = 'complete'
        """
        rows = conn.execute(sql, (sector, perspective)).fetchall()
        out: dict[str, dict[str, int]] = {}
        for r in rows:
            out.setdefault(r["ticker"], {})[r["force"]] = r["score"]
        return out
    finally:
        if own:
            conn.close()


def get_macro_snapshot(
    geography: str,
    period: str,
    max_age_days: int = 14,
    conn: Optional[sqlite3.Connection] = None,
) -> Optional[dict]:
    """Return the 6-factor row for (geo, period) if any was collected within max_age_days, else None."""
    own = conn is None
    if own:
        try:
            conn = open_conn()
        except FileNotFoundError:
            return None
    try:
        sql = """
            SELECT factor_slot, factor_name_raw, current_value, forecast_value,
                   factor_change_pct, beta, phi, adjustment_pct, unit, source,
                   collected_at, source_run_id
              FROM macro_factors_period
             WHERE geography = ? AND period = ?
               AND julianday('now') - julianday(collected_at) <= ?
             ORDER BY collected_at DESC
        """
        rows = conn.execute(sql, (geography, period, max_age_days)).fetchall()
        if not rows:
            return None
        snapshot: dict[str, dict] = {"geography": geography, "period": period, "factors": {}}
        for r in rows:
            slot = r["factor_slot"]
            if slot not in snapshot["factors"]:
                snapshot["factors"][slot] = dict(r)
        if len(snapshot["factors"]) < 6:
            return None
        return snapshot
    finally:
        if own:
            conn.close()


def search_signals(query: str, sector: Optional[str] = None, limit: int = 20, conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    own = conn is None
    if own:
        try:
            conn = open_conn()
        except FileNotFoundError:
            return []
    try:
        if sector:
            sql = """
                SELECT i.* FROM intelligence_signals i
                  JOIN fts_narratives f ON f.doc_id = ('signal:' || i.sig_id)
                 WHERE i.sector = ? AND fts_narratives MATCH ?
                 LIMIT ?
            """
            return _rows(conn.execute(sql, (sector, query, limit)))
        sql = """
            SELECT i.* FROM intelligence_signals i
              JOIN fts_narratives f ON f.doc_id = ('signal:' || i.sig_id)
             WHERE fts_narratives MATCH ?
             LIMIT ?
        """
        return _rows(conn.execute(sql, (query, limit)))
    finally:
        if own:
            conn.close()


def search_disclosure_quirks(sector: str, limit: int = 10, conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    own = conn is None
    if own:
        try:
            conn = open_conn()
        except FileNotFoundError:
            return []
    try:
        sql = "SELECT * FROM disclosure_quirks WHERE sector = ? ORDER BY rowid DESC LIMIT ?"
        return _rows(conn.execute(sql, (sector, limit)))
    finally:
        if own:
            conn.close()


def search_narratives(
    query: str,
    section: Optional[str] = None,
    ticker: Optional[str] = None,
    limit: int = 10,
    conn: Optional[sqlite3.Connection] = None,
) -> list[dict]:
    own = conn is None
    if own:
        try:
            conn = open_conn()
        except FileNotFoundError:
            return []
    try:
        clauses = ["fts_narratives MATCH ?"]
        params: list = [query]
        if section:
            clauses.append("section = ?")
            params.append(section)
        if ticker:
            clauses.append("ticker = ?")
            params.append(ticker)
        sql = f"SELECT doc_id, ticker, sector, section, snippet(fts_narratives, 4, '<<', '>>', '…', 12) AS snippet FROM fts_narratives WHERE {' AND '.join(clauses)} LIMIT ?"
        params.append(limit)
        return _rows(conn.execute(sql, params))
    finally:
        if own:
            conn.close()


def get_run_history(ticker: str, conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    own = conn is None
    if own:
        try:
            conn = open_conn()
        except FileNotFoundError:
            return []
    try:
        sql = "SELECT * FROM runs WHERE ticker = ? ORDER BY run_date DESC"
        return _rows(conn.execute(sql, (ticker,)))
    finally:
        if own:
            conn.close()


def get_peer_revenue_growth(sector: str, fiscal_period: str, conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    own = conn is None
    if own:
        try:
            conn = open_conn()
        except FileNotFoundError:
            return []
    try:
        sql = """
            SELECT fp.ticker, fp.fiscal_period, fp.revenue, fp.yoy_revenue_pct
              FROM financials_period fp
              JOIN companies c ON c.ticker = fp.ticker
              JOIN runs r ON r.run_id = fp.source_run_id
             WHERE c.sector = ? AND fp.fiscal_period = ?
               AND r.run_status = 'complete'
             ORDER BY fp.yoy_revenue_pct DESC
        """
        return _rows(conn.execute(sql, (sector, fiscal_period)))
    finally:
        if own:
            conn.close()


def get_sector_macro_consistency(sector: str, period: str, conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    own = conn is None
    if own:
        try:
            conn = open_conn()
        except FileNotFoundError:
            return []
    try:
        sql = """
            SELECT DISTINCT m.*
              FROM macro_factors_period m
             WHERE m.period = ?
               AND m.geography IN (
                   SELECT DISTINCT primary_geography FROM companies WHERE sector = ?
               )
        """
        return _rows(conn.execute(sql, (period, sector)))
    finally:
        if own:
            conn.close()


# ─────────────────────────────────────────────────────────────────────
# CLI: dump P0_DB_PRECHECK output for a given ticker
# ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="DB pre-check for a run.")
    p.add_argument("--ticker", required=True)
    p.add_argument("--sector", default=None)
    p.add_argument("--geography", default=None)
    p.add_argument("--period", default=None, help="fiscal period like FY2026Q2 (for macro snapshot lookup)")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--out", default=None, help="Write result to this path; else stdout")
    args = p.parse_args(argv)

    try:
        conn = open_conn(args.db)
    except FileNotFoundError:
        out = {
            "ticker": args.ticker,
            "status": "no_db",
            "prior_financials": [],
            "peer_companies": [],
            "macro_snapshot": None,
        }
        text = json.dumps(out, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text, encoding="utf-8")
        print(text)
        return 0

    try:
        priors = get_prior_financials(args.ticker, n=4, conn=conn)
        peers = get_peer_companies(args.ticker, args.sector, args.geography, conn=conn)
        macro = (
            get_macro_snapshot(args.geography, args.period, conn=conn)
            if args.geography and args.period
            else None
        )
        out = {
            "ticker": args.ticker,
            "status": "ok" if (priors or peers or macro) else "no_priors",
            "prior_financials": priors,
            "peer_companies": peers,
            "macro_snapshot": macro,
        }
        text = json.dumps(out, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text, encoding="utf-8")
        print(text)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
