from __future__ import annotations

import json
from pathlib import Path

from tools.audit.user_agent_pii import audit_run


def _seed_run(tmp_path: Path, *, public_user_agent: str | None = "EquityResearchSkill/1.0") -> Path:
    run_dir = tmp_path / "Run"
    (run_dir / "meta").mkdir(parents=True)
    (run_dir / "logs").mkdir()
    email = "user@example-real.com"
    run_meta = {
        "run_id": "ua1",
        "ticker": "INTU",
        "sec_email": email,
        "sec_user_agent": f"EquityResearchSkill/1.0 ({email})",
    }
    if public_user_agent is not None:
        run_meta["public_user_agent"] = public_user_agent
    (run_dir / "meta" / "run.json").write_text(json.dumps(run_meta), encoding="utf-8")
    return run_dir


def test_user_agent_pii_passes_sec_only_email_logs(tmp_path: Path) -> None:
    run_dir = _seed_run(tmp_path)
    (run_dir / "logs" / "requests.log").write_text(
        "GET https://data.sec.gov/submissions/CIK0000896878.json "
        "UA=EquityResearchSkill/1.0 (user@example-real.com)\n"
        "GET https://investors.intuit.com/ UA=EquityResearchSkill/1.0\n",
        encoding="utf-8",
    )

    result = audit_run(run_dir)

    assert result["status"] == "pass"
    assert result["violations"] == []


def test_user_agent_pii_fails_missing_public_user_agent(tmp_path: Path) -> None:
    run_dir = _seed_run(tmp_path, public_user_agent=None)

    result = audit_run(run_dir)

    assert result["status"] == "fail"
    assert any("public_user_agent" in error for error in result["errors"])


def test_user_agent_pii_fails_email_on_non_sec_url(tmp_path: Path) -> None:
    run_dir = _seed_run(tmp_path)
    (run_dir / "meta" / "run.jsonl").write_text(
        '{"event":"fetch","url":"https://investors.intuit.com/news",'
        '"user_agent":"EquityResearchSkill/1.0 (user@example-real.com)"}\n',
        encoding="utf-8",
    )

    result = audit_run(run_dir)

    assert result["status"] == "fail"
    assert result["violations"][0]["non_sec_urls"] == ["https://investors.intuit.com/news"]


def test_user_agent_pii_passes_without_active_sec_email(tmp_path: Path) -> None:
    run_dir = tmp_path / "Run"
    (run_dir / "meta").mkdir(parents=True)
    (run_dir / "meta" / "run.json").write_text(
        json.dumps({"sec_email": "declined", "sec_user_agent": None}),
        encoding="utf-8",
    )

    result = audit_run(run_dir)

    assert result["status"] == "pass"
    assert result["sec_email_present"] is False
