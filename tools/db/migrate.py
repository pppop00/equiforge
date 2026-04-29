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
