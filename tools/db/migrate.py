"""Apply numbered SQL migrations from db/schema/*.sql to db/equity_kb.sqlite.

Idempotent: reads PRAGMA user_version and only applies higher-numbered migrations.

Usage:
    python tools/db/migrate.py                       # default db at db/equity_kb.sqlite
    python tools/db/migrate.py --db /tmp/test.sqlite # different file
    python tools/db/migrate.py --dry-run             # show what would apply
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "db" / "equity_kb.sqlite"
SCHEMA_DIR = PROJECT_ROOT / "db" / "schema"

MIGRATION_RE = re.compile(r"^(\d{3})_.*\.sql$")
ADD_COLUMN_RE = re.compile(
    r"^\s*ALTER\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)\s+ADD\s+COLUMN\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)\s+(.+?)\s*;?\s*$",
    re.IGNORECASE | re.DOTALL,
)


def discover_migrations() -> list[tuple[int, Path]]:
    out: list[tuple[int, Path]] = []
    for f in sorted(SCHEMA_DIR.glob("*.sql")):
        m = MIGRATION_RE.match(f.name)
        if not m:
            continue
        out.append((int(m.group(1)), f))
    return out


def current_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def apply_migrations(db_path: Path, dry_run: bool = False) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        installed = current_version(conn)
        migrations = discover_migrations()
        pending = [m for m in migrations if m[0] > installed]
        applied: list[int] = []
        if dry_run:
            return {"db": str(db_path), "current": installed, "pending": [m[0] for m in pending], "applied": []}
        for version, path in pending:
            sql = path.read_text(encoding="utf-8")
            try:
                if not _apply_add_column_migration(conn, sql):
                    conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_meta (schema_version, applied_at, notes) VALUES (?, ?, ?)",
                    (version, _now_iso(), path.name),
                )
                conn.execute(f"PRAGMA user_version = {version}")
                conn.commit()
                applied.append(version)
            except sqlite3.Error as e:
                conn.rollback()
                raise RuntimeError(f"migration {path.name} failed: {e}") from e
        return {
            "db": str(db_path),
            "previous_version": installed,
            "applied": applied,
            "current_version": current_version(conn),
        }
    finally:
        conn.close()


def _apply_add_column_migration(conn: sqlite3.Connection, sql: str) -> bool:
    """Apply simple additive-column migrations idempotently.

    SQLite has no `ALTER TABLE ADD COLUMN IF NOT EXISTS`; this keeps additive
    schema migrations safe when a short-lived bad migration already created a
    column but did not advance `PRAGMA user_version`.
    """
    statements = _sql_statements_without_line_comments(sql)
    if not statements:
        return False

    parsed: list[tuple[str, str, str]] = []
    for statement in statements:
        m = ADD_COLUMN_RE.match(statement)
        if not m:
            return False
        parsed.append((m.group(1), m.group(2), m.group(3)))

    for table, column, definition in parsed:
        columns = {
            row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column in columns:
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    return True


def _sql_statements_without_line_comments(sql: str) -> list[str]:
    body = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    return [part.strip() for part in body.split(";") if part.strip()]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        result = apply_migrations(Path(args.db), dry_run=args.dry_run)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    import json
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
