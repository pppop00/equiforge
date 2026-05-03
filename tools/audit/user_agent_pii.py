"""P12 privacy audit for SEC vs public User-Agent separation.

The SEC EDGAR User-Agent may contain the user's contact email. That string must
only be used for SEC endpoints. Public/third-party fetches must use a PII-free
User-Agent.

Usage:
    python tools/audit/user_agent_pii.py --run-dir <path>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s\"'<>),]+")
PUBLIC_USER_AGENT = "EquityResearchSkill/1.0"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _normalise_email(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.lower() in {"", "declined", "skipped", "none", "n/a", "no_email"}:
        return None
    return value if EMAIL_RE.fullmatch(value) else None


def _gate_payload(gates: dict) -> dict:
    payload = gates.get("P0_sec_email") if isinstance(gates, dict) else None
    return payload if isinstance(payload, dict) else {}


def _is_sec_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "sec.gov" or host.endswith(".sec.gov")


def _candidate_log_files(run_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    meta_log = run_dir / "meta" / "run.jsonl"
    if meta_log.exists():
        candidates.append(meta_log)

    for dirname in ("logs", "request_logs"):
        root = run_dir / dirname
        if root.exists():
            candidates.extend(p for p in root.rglob("*") if p.is_file())

    for dirname in ("validation", "research"):
        root = run_dir / dirname
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            if any(token in name for token in ("request", "fetch", "http", "log")):
                candidates.append(path)

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def _scan_logs(run_dir: Path, email: str) -> tuple[list[dict], list[str], int]:
    violations: list[dict] = []
    warnings: list[str] = []
    files_scanned = 0

    for path in _candidate_log_files(run_dir):
        try:
            if path.stat().st_size > 20_000_000:
                warnings.append(f"skipped large request log: {path}")
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            warnings.append(f"could not read request log {path}: {exc}")
            continue

        files_scanned += 1
        for line_no, line in enumerate(text.splitlines(), start=1):
            if email not in line:
                continue
            urls = URL_RE.findall(line)
            non_sec_urls = [url for url in urls if not _is_sec_url(url)]
            if non_sec_urls:
                violations.append(
                    {
                        "file": str(path),
                        "line": line_no,
                        "non_sec_urls": non_sec_urls[:5],
                        "reason": "SEC email appeared on a line with non-SEC URL(s)",
                    }
                )

    return violations, warnings, files_scanned


def audit_run(run_dir: Path) -> dict:
    run_dir = run_dir.resolve()
    run_meta = _load_json(run_dir / "meta" / "run.json")
    gates = _load_json(run_dir / "meta" / "gates.json")
    gate = _gate_payload(gates)

    sec_email = _normalise_email(run_meta.get("sec_email")) or _normalise_email(gate.get("value"))
    sec_user_agent = run_meta.get("sec_user_agent", gate.get("sec_user_agent"))
    public_user_agent = run_meta.get("public_user_agent", gate.get("public_user_agent"))

    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict] = []

    if not sec_email:
        status = "pass"
        checks.append({"id": "active_sec_email", "status": "pass", "detail": "no active SEC email in run metadata"})
        return {
            "schema_version": 1,
            "status": status,
            "sec_email_present": False,
            "public_user_agent": public_user_agent,
            "checks": checks,
            "violations": [],
            "warnings": warnings,
            "files_scanned": 0,
        }

    if not isinstance(sec_user_agent, str) or sec_email not in sec_user_agent:
        errors.append("sec_user_agent must be present and contain the SEC email for SEC EDGAR requests")
        checks.append({"id": "sec_user_agent_contains_email", "status": "fail"})
    else:
        checks.append({"id": "sec_user_agent_contains_email", "status": "pass"})

    if not isinstance(public_user_agent, str) or not public_user_agent.strip():
        errors.append("public_user_agent must be present when sec_email is active")
        checks.append({"id": "public_user_agent_present", "status": "fail"})
    else:
        checks.append({"id": "public_user_agent_present", "status": "pass"})
        if EMAIL_RE.search(public_user_agent):
            errors.append("public_user_agent must not contain any email address")
            checks.append({"id": "public_user_agent_pii_free", "status": "fail"})
        else:
            checks.append({"id": "public_user_agent_pii_free", "status": "pass"})

    violations, scan_warnings, files_scanned = _scan_logs(run_dir, sec_email)
    warnings.extend(scan_warnings)
    if violations:
        errors.append("SEC email appeared in request logs next to non-SEC URL(s)")
        checks.append({"id": "non_sec_request_log_email_scan", "status": "fail", "violations": len(violations)})
    else:
        checks.append({"id": "non_sec_request_log_email_scan", "status": "pass", "files_scanned": files_scanned})

    return {
        "schema_version": 1,
        "status": "fail" if errors else ("warn" if warnings else "pass"),
        "sec_email_present": True,
        "public_user_agent": public_user_agent,
        "recommended_public_user_agent": PUBLIC_USER_AGENT,
        "checks": checks,
        "violations": violations,
        "errors": errors,
        "warnings": warnings,
        "files_scanned": files_scanned,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    result = audit_run(Path(args.run_dir))
    out_path = Path(args.out).resolve() if args.out else Path(args.run_dir).resolve() / "validation" / "user_agent_pii.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
