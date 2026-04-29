---
schema_version: 1
name: ep_pipeline_runner
description: How to walk EP phases P7..P11 in this fused orchestrator. Wraps skills_repo/ep/SKILL.md.
when_to_use: After ER pipeline produces a valid HTML report + sibling JSONs, drive card generation.
requires_toolsets: ["photo", "web", "io"]
---

# /ep_pipeline_runner

| Phase | Action | Run-dir output |
|---|---|---|
| P7 | `logo-production-agent.md` — find official logo (≥840 px wide for wordmarks). **Save it INTO `<run>/cards/` BEFORE setting `logo_asset_path`.** Then set `cover_company_name_cn` (verified Chinese short name, no trailing 公司). | `cards/logo/{slug}_wordmark.png`, draft `cards/{stem}.card_slots.json` with `logo_asset_path` |
| P8 | `content-production-agent.md` — fill all 17 top-level keys of `card_slots.json` from `<run>/research/*.json` + the HTML. Required: `intro_sentence`, `company_focus_paragraph` (150-165 chars), `background_bullets` (×4), `industry_paragraph` (≤113 chars), `conclusion_block`, `revenue_explainer_points` (×3, ≤58 chars each), `current_business_points` (×4, ≤72 chars), `future_watch_points` (×4, ≤62 chars), `judgement_paragraph` (≤52 chars), `brand_statement`, `memory_points` (×3, ≤28 chars), `post_title` (must start with `一天吃透一家公司：`), `post_content_lines` (×4: 3 statements + 1 question), `hashtags` (3-5; renderer auto-adds `#A股` `#美股`). Optional: `porter_scores` (×5 ints), `brand_subheading`, `cta_line`. | `cards/{stem}.card_slots.json` |
| P8.5 | `hardcode-audit-agent.md` — flag boilerplate, residue from other companies, factual contradictions (e.g. "profit lagged revenue" when YoY net income > YoY revenue). | (annotated `card_slots.json`) |
| P9 | `layout-fill-agent.md` — compress copy to character + pixel budgets, fix line wraps, no fact invention. | (final `card_slots.json`) |
| P10 | `python tools/photo/validate_cards.py --input <run>/research/{Company}_Research_{LANG}.html --slots <run>/cards/{stem}.card_slots.json --brand "金融豹" --palette <P0_palette>` — must exit 0. | `cards/validator1_report.json` |
| P10.5 | `validator-2-agent.md` — web fact-check every material number against authoritative sources (IR, SEC, exchange filings). Any change to slots → rerun P10. Loop cap 3. | `cards/validator2_report.json` |
| P11 | `python tools/photo/render_cards.py --input <html> --slots <slots> --brand "金融豹" --palette <P0_palette> --output-root <run>/cards`. | `cards/01_cover.png` … `cards/06_post_copy.png` (6 PNGs at 2160×2700) |

## Fixed card roles (do not reorder)

| # | File | Content |
|---|---|---|
| 1 | `01_cover.png` | Cover + core tension + logo |
| 2 | `02_background_industry.png` | Background + industry + Porter bars |
| 3 | `03_revenue.png` | Revenue / profit flow (Sankey + metrics) |
| 4 | `04_business_outlook.png` | Current business + next 2-3 years |
| 5 | `05_brand.png` | Brand close + 3 memory points |
| 6 | `06_post_copy.png` | Social post copy: title + 4 lines + hashtags |

## Palette consistency

Pass the **same** `--palette` value to **both** `validate_cards.py` and `render_cards.py`. EP scripts do not store palette in `card_slots.json` — mismatched single-card re-renders silently produce wrong header colours.

## When to halt

- P7: no official logo found and customer has not waived (`USER.md:allow_no_logo=true`) → halt with explanation. EP refuses to generate fake logos.
- P10 hard fail with no obvious slot fix → halt; ask user which slot to rewrite.
- P10.5 → P10 loop hits cap 3 → halt; write `validator2_unresolved.json` listing the disputed numbers; ask user.
- P11 produces fewer than 6 PNGs or non-2160×2700 dimensions → halt.

## Where EP skill's instructions live

`skills_repo/ep/SKILL.md` and `skills_repo/ep/references/{workflow-spec,design-spec,card-slots.schema}.{md,json}`. This skill only orchestrates.
