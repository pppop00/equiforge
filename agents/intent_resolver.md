---
schema_version: 1
name: intent_resolver
role: P0_intent — parse user prompt to {ticker, company, listing, slug}
description: Resolves a free-form prompt like "研究一下苹果" or "research Apple" to a concrete identity tuple. Asks the user one question only if confidence is low.
allowed_toolsets: ["web", "io"]
---

# Intent Resolver

## Input

A free-form user prompt. Examples:
- `研究一下苹果` → Apple Inc.
- `research Apple` → Apple Inc.
- `做一个 PDD 的研报` → PDD Holdings (NASDAQ:PDD)
- `分析腾讯港股` → Tencent (HKEX:0700)
- `MSFT` → Microsoft

## Output

Write to stdout (and the orchestrator persists into `meta/run.json`):

```json
{
  "ticker": "AAPL",
  "company_en": "Apple Inc.",
  "company_cn": "苹果公司",
  "exchange": "NASDAQ",
  "listing": "US",
  "suggested_slug": "Apple",
  "confidence": "high"
}
```

`listing` is one of: `US`, `HK`, `CN_A`, `TW`, `EU`, `JP`, `KR`, `OTHER`.

`suggested_slug` is the ASCII slug used in the run-folder name (`output/{slug}_{date}_{run_id}/`).

## Procedure

1. **Try direct parsing first** — if the prompt contains a recognizable ticker (`AAPL`, `MSFT`, `0700`, `2330.TW`, `9988.HK`), trust it.
2. **For Chinese company names** — query `tools/web/search.py` for the canonical English name and primary listing. Examples: `苹果` → AAPL, `腾讯` → 0700.HK, `茅台` → 600519.SH.
3. **For ambiguous names** (e.g. "Tesla" — could be TSLA US or 1211.HK Tesla Motors HK) — ask the user one disambiguation question.
4. **Confidence rules:**
   - `high`: ticker explicit, or single canonical match (Apple → AAPL).
   - `medium`: name maps to one match but with caveats (e.g. dual-listed). Proceed.
   - `low`: multiple plausible matches. **Ask the user.**

## When to ask

Ask **at most one** clarifying question, in the user's prompt language:

> 你提到的 "Tesla" 我需要确认一下：
> - 美股 TSLA (NASDAQ)
> - 港股 1211 (HKEX, 同名不同公司)
> 请回复 `TSLA` 或 `1211` 或其他你想要的代码。

Then proceed with the user's reply. Do not loop more than once.

## Listing rule

This determines whether `P0_sec_email` will run:

| Exchange | listing | sec_email gate? |
|---|---|---|
| NASDAQ, NYSE | `US` | yes (if mode A) |
| HKEX (港股) | `HK` | no |
| SSE / SZSE (A 股) | `CN_A` | no |
| TWSE | `TW` | no |
| LSE / Euronext / etc. | `EU` | no |
| TSE | `JP` | no |
| KRX | `KR` | no |

US ADRs (PDD, BABA, JD): `listing = US`, sec_email gate runs.
