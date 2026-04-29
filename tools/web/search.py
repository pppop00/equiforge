"""Web search facade.

This is a stub. The actual search backend depends on the host environment:

- In Claude Code / Cursor: the host LLM has WebSearch / WebFetch tools — the orchestrator
  should call those directly instead of invoking this script.
- For headless / batch use: implement a backend (e.g. Brave Search API, SerpAPI) and
  swap in via the SEARCH_BACKEND env var.

This script exists so agent briefs can reference a stable command name. When called
without a backend configured, it prints a clear error and a hint instead of failing
silently.
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def search(query: str, k: int = 5) -> list[dict]:
    backend = os.environ.get("SEARCH_BACKEND", "").lower()
    if not backend or backend == "host":
        print(
            json.dumps(
                {
                    "error": "no_backend",
                    "hint": "This script is a stub. In Claude Code / Cursor, call the host's WebSearch tool directly. "
                            "For headless use, set SEARCH_BACKEND=brave|serpapi and implement the backend.",
                    "query": query,
                }
            ),
            file=sys.stderr,
        )
        sys.exit(3)
    raise NotImplementedError(f"backend {backend!r} not yet wired")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--query", required=True)
    p.add_argument("-k", type=int, default=5)
    args = p.parse_args(argv)
    results = search(args.query, args.k)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
