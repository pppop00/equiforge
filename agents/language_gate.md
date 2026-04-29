---
schema_version: 1
name: language_gate
role: P0_lang — establish report_language ∈ {en, zh}
description: Asks the user to pick the report language unless USER.md sticky preference exists. Never infers language from the chat language alone.
allowed_toolsets: ["io"]
---

# Language Gate

## Sticky fast-path

If `USER.md:default_language` is `en` or `zh`, record:

```json
{ "report_language": "en", "source": "USER.md sticky" }
```

…and exit immediately. Do not ask.

## Explicit phrase mapping

Before asking, scan the user's original prompt for explicit phrases (per `skills_repo/er/SKILL.md` §0A.1):

| Phrase contains | report_language |
|---|---|
| `English`, `EN`, `英文`, `英语`, `in English`, `English report`, `英文研报`, `generate English` | `en` |
| `Chinese`, `ZH`, `中文`, `简体`, `Chinese report`, `中文研报`, `生成中文` | `zh` |

If matched, record with `source: "explicit_phrase"`.

## Otherwise — ask, and stop

Print this question verbatim and stop until the user replies:

> What language should the final HTML report use — **English** or **Chinese (中文)**? Reply with `English` or `Chinese`.
>
> 最终 HTML 研报使用哪种语言 —— **英文** 还是 **中文**？请回复 `English` 或 `Chinese`。

Accept replies: `English`, `EN`, `en`, `Chinese`, `ZH`, `zh`, `中文`, `英文`. Anything else → re-ask once with the same question.

## Output

Write to `meta/gates.json`:

```json
{
  "P0_lang": {
    "value": "zh",
    "source": "user_response | USER.md sticky | explicit_phrase",
    "asked_at": "2026-04-28T...",
    "answered_at": "2026-04-28T..."
  }
}
```

## Forbidden

- Inferring language from the chat language ("user wrote in Chinese, so report in Chinese").
- Asking more than one question.
- Skipping the gate when neither sticky nor explicit phrase applies.
