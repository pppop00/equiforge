---
schema_version: 1
name: sec_email_gate
role: P0_sec_email — capture real email for SEC EDGAR User-Agent or accept explicit decline
description: Only runs when listing=US and mode A (no PDFs). Implements skills_repo/er/SKILL.md §0A.2 verbatim.
allowed_toolsets: ["io"]
---

# SEC Email Gate

## Skip conditions

Skip and record `P0_sec_email = "skipped"` with `reason` if any of:
- `meta/run.json:listing != "US"` (HK / A-share / EU / etc.)
- mode is B or C (user uploaded PDFs)
- `USER.md:default_sec_email` is set (sticky)

## Sticky fast-path

If `USER.md:default_sec_email` exists:
- Value is a plausible email (regex `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}`, not on the placeholder list) → use it. Set `sec_user_agent = "EquityResearchSkill/1.0 (<that_email>)"` and `public_user_agent = "EquityResearchSkill/1.0"`.
- Value is `decline` / `不提供` / `no_email` → set `sec_email = "declined"`, `sec_user_agent = null`, and `public_user_agent = "EquityResearchSkill/1.0"`.

Either way, record `source: "USER.md sticky"` and exit.

## Otherwise — ask in `report_language`

If `report_language == "en"`:

> SEC EDGAR API requires a real contact email in the User-Agent. Please reply with one email (used only as `EquityResearchSkill/1.0 (you@domain.com)` for this run). If you do not want to provide one, reply `no email`.

If `report_language == "zh"`:

> 若走 SEC EDGAR 接口，需在请求头中包含真实邮箱。请回复一个邮箱（仅用于本轮标识）。若不愿提供，请回复 `不提供邮箱`。

## Validation

Reject obvious placeholders with **one** re-ask:
- `example.com`, `example.org`, `test.com`
- `test@test`, `user@localhost`, `a@a`, `foo@bar`
- Anything matching `(no-?reply|admin|info|contact)@`

Pattern: standard email regex + length 5–254 + a real-looking TLD (≥2 chars).

If the user replies anything not parseable as an email and not in the decline list, re-ask once. Second non-answer → set `declined` and proceed.

## Decline phrases

Accept `no email`, `decline`, `not now`, `不提供`, `不提供邮箱`, `no_email`, `none`, `n/a` as decline.

## Output

```json
{
  "P0_sec_email": {
    "value": "user@example-real.com",          // or "declined"
    "sec_user_agent": "EquityResearchSkill/1.0 (user@example-real.com)",   // or null
    "public_user_agent": "EquityResearchSkill/1.0",
    "source": "user_response | USER.md sticky | skipped",
    "skip_reason": "listing != US"             // only if skipped
  }
}
```

Append to `meta/gates.json`. **The email itself is never written to `db/equity_kb.sqlite`** — see `MEMORY.md` privacy invariants.

Also persist both `sec_user_agent` and `public_user_agent` into `meta/run.json`. `sec_user_agent` is only for SEC EDGAR endpoints (`sec.gov` hosts). Every non-SEC outbound HTTP request must use `public_user_agent`, which must contain no email or other PII.

`source` is a closed enum: `user_response`, `USER.md sticky`, or `skipped` (only when `applies_when` returns false). Auto-mode is not a license to skip this gate — never invent values like `auto_mode_default`. If the user has not replied and no sticky default exists and `applies_when` is true, halt and wait.

## Pass-down to Agent 1

When delegating to `skills_repo/er/agents/financial_data_collector.md`, include exactly one line in the task prompt:
- `Financial data SEC API: yes` and `SEC_EDGAR_USER_AGENT: EquityResearchSkill/1.0 (user@example-real.com)`, or
- `Financial data SEC API: no`

When delegating to any agent that may fetch non-SEC pages (news, IR pages, logo/image hosts, peer pages), include:
- `PUBLIC_USER_AGENT: EquityResearchSkill/1.0`

Do not pass `SEC_EDGAR_USER_AGENT` to non-SEC fetchers as their default User-Agent.
