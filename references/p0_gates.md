---
schema_version: 1
description: Per-gate rules for the four P0 gates (intent, language, SEC email, palette). Read this when entering any P0 gate or when reviewing meta/gates.json.
---

# P0 gates — per-gate rules

The four P0 gates are all **blocking** and **not skippable**, but they split into two kinds:

- **Resolution gate** — `P0_intent`. Resolves identity from the prompt. Auto-resolution is allowed (and expected) when the prompt is unambiguous; user is asked only on ambiguity.
- **Interactive gates** — `P0_lang`, `P0_sec_email`, `P0_palette`. Cannot be inferred from the prompt. Each must be satisfied by either a real user reply or a sticky value in `USER.md`. Auto-mode does not waive them. The cost of guessing wrong (wrong-language report, missing SEC User-Agent, wrong palette across 6 cards) is a full re-run.

Each gate's answer is recorded in `meta/gates.json` with a `source` field. Only the values listed below are allowed per gate; anything else is a P0 violation and will be caught in `meta/gates.json` review.

## P0_intent (resolution gate)

- **Goal**: resolve the user's prompt to `{ticker, company, listing}` (and a suggested URL slug).
- **Agent**: `agents/intent_resolver.md`.
- **Interactive?** Only when confidence is low — ask **once**, then use the user's answer. Otherwise resolve from the prompt and proceed.
- **Allowed `source` values**: `prompt_unambiguous` (resolved from the prompt), `user_response` (asked because of ambiguity).
- **Why this gate is different**: the answer *is* derivable from the prompt in the common case. The other three gates exist precisely because their answers are not.

## P0_lang (interactive gate)

- **Goal**: `report_language ∈ {en, zh}`.
- **Agent**: `agents/language_gate.md`.
- **Sticky source**: `USER.md:default_language`.
- **Inference**: only the explicit phrases listed in `skills_repo/er/SKILL.md` §0A.1 may be used. **Do not** infer from the language of the chat alone.
- **Allowed `source` values**: `user_response`, `USER.md sticky`, `explicit_phrase` (one of the whitelisted phrases appeared in the original prompt).
- **Halt** until you have one of the above.

## P0_sec_email (interactive gate)

- **Goal**: a real email for the SEC EDGAR `User-Agent` header, or an explicit decline; plus a PII-free `public_user_agent` for every non-SEC fetch.
- **Agent**: `agents/sec_email_gate.md`.
- **Sticky source**: `USER.md:default_sec_email`.
- **`applies_when`**: `listing == "US"` AND `mode == "A"` (no PDFs uploaded) AND no sticky in `USER.md`.
- **Reject** placeholders: `example.com`, `test@test`, `user@localhost` — re-ask once.
- **Privacy**: this email is **never** persisted to the DB. It may appear in `meta/run.json` / `meta/gates.json` only as `sec_email` and `sec_user_agent`, and must be used only for SEC EDGAR hosts. `public_user_agent` must be present, must contain no email, and is the only allowed User-Agent for logo, IR, news, peer, image, and other third-party fetches. P12 enforces this with `tools/audit/user_agent_pii.py`.
- **Allowed `source` values**: `user_response`, `USER.md sticky`, `skipped` (when `applies_when` is false), `declined`.

## P0_palette (interactive gate)

- **Goal**: `palette ∈ {macaron, default, b, c}`.
- **Agent**: `agents/palette_gate.md`.
- **Sticky source**: `USER.md:default_palette`.
- **Why it blocks**: the palette is **not** stored in `card_slots.json`; mismatched single-card re-renders cause silent header-colour drift across the 6-card pack. All six cards in one run must use the same `--palette`.
- **Allowed `source` values**: `user_response`, `USER.md sticky`.

## What never counts as a valid source (interactive gates only)

`auto_mode_default`, `assumed_from_chat_language`, `inferred_from_locale`, `prefilled_for_speed`, or any other invented value. The interactive gates exist because the answer is not derivable from context — inventing one defeats the gate.

The resolution gate (`P0_intent`) is different: `prompt_unambiguous` *is* a valid source there, because identity often is derivable from the prompt. The line between the two is sharp on purpose.
