"""Append a phase event to <run_dir>/meta/run.jsonl.

Usage:
    python tools/io/event_log.py --run-dir <path> --phase P0_intent --event phase_enter
    python tools/io/event_log.py --run-dir <path> --phase P0_intent --event phase_exit \
        --payload '{"ticker":"AAPL","confidence":"high"}'

The log is JSONL, append-only, atomic per line (one fsync per write).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def append_event(run_dir: Path, phase: str, event: str, payload: dict | None = None) -> dict:
    run_dir = Path(run_dir).resolve()
    log = run_dir / "meta" / "run.jsonl"
    if not log.parent.exists():
        raise FileNotFoundError(f"meta/ does not exist under {run_dir}; was run_dir.py run?")
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "phase": phase,
        "event": event,
        "payload": payload or {},
    }
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    with log.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
    return rec


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--phase", required=True)
    p.add_argument("--event", required=True, help="e.g. phase_enter | phase_exit | phase_failed | tool_call")
    p.add_argument("--payload", default="{}", help="JSON string")
    args = p.parse_args(argv)
    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as e:
        print(f"error: --payload is not valid JSON: {e}", file=sys.stderr)
        return 2
    rec = append_event(Path(args.run_dir), args.phase, args.event, payload)
    print(json.dumps(rec, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
