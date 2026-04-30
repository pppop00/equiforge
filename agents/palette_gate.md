---
schema_version: 1
name: palette_gate
role: P0_palette — establish palette ∈ {macaron, default, b, c}
description: Asks the user to pick a card colour palette. Required before any EP work. EP scripts have no fallback — palette must be explicitly passed.
allowed_toolsets: ["io"]
---

# Palette Gate

## Sticky fast-path

If `USER.md:default_palette` is one of `macaron`, `default`, `b`, `c`, record with `source: "USER.md sticky"` and exit.

## Otherwise — ask

In `report_language`:

**EN:**
> Which card palette should we use? Reply with one of:
> - `macaron` — warm cream canvas, dark header, pastel accents
> - `default` — gray-white canvas, light header, red-orange accents (legacy)
> - `b` — soft violet canvas, light header, purple/emerald accents (Xiaohongshu-friendly)
> - `c` — warm paper canvas, dark header, magazine style

**ZH:**
> 卡片配色用哪一组？回复以下之一：
> - `macaron` — 暖米色背景 + 深色头部 + 马卡龙强调色
> - `default` — 灰白背景 + 浅色头部 + 红橙强调（旧版）
> - `b` — 浅紫背景 + 浅色头部 + 紫色/翠绿强调（小红书风）
> - `c` — 暖纸色背景 + 深色头部（杂志风）

## Validation

Accept exact match (case-insensitive) of one of the four values. Anything else → re-ask once.

## Output

```json
{
  "P0_palette": {
    "value": "macaron",
    "source": "user_response | USER.md sticky"
  }
}
```

`source` is a closed enum: exactly `user_response` or `USER.md sticky`. Do **not** invent values like `auto_mode_default`, `assumed`, or `inferred`. Auto-mode is not a license to skip this gate — palette propagates through 6 PNGs and a wrong choice means a full re-render. If the user has not replied and no sticky default exists, halt and wait. The orchestrator passes this value to **both** `tools/photo/validate_cards.py --palette` and `tools/photo/render_cards.py --palette` for every card render in this run.

## Single-card re-render trap

If the user later asks to re-render only card 3, the orchestrator must pass the **same** palette as the original 6-card render. EP scripts do not store palette in `card_slots.json`; mismatch causes silent header colour drift and Validator cannot detect it.
