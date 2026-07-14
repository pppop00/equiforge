# Non-blocking human reader test

This study measures whether the five-card knowledge map teaches the intended ideas. It is product research, not a release or database-index gate.

## Participants and timing

- Recruit at least five real readers who did not help create the cards.
- Give each reader Card 1–5 for exactly 60 seconds, then remove the cards.
- Run the immediate prompt below without hints.
- Seven days later, repeat the same prompt without showing the cards first.
- An agent must not impersonate, simulate, or synthesize participants.

## Prompt and scoring

Ask: “In one minute, explain how the company makes money, name the two variables that most affect its results, and state its primary risk.”

Score each element against the card's intended meaning, not exact wording:

- `business_model`: 0 or 1
- `core_variable_1`: 0 or 1
- `core_variable_2`: 0 or 1
- `primary_risk`: 0 or 1

Record one anonymized participant ID, the four scores, and optional verbatim notes for the immediate and seven-day sessions. Do not store names, email addresses, or contact details in the run directory or knowledge database.

## Optional artifact

If the study is completed, save `validation/reader_test.json` with `participant_count`, `immediate_results`, `day_7_results`, and `study_date`. Missing or incomplete reader testing remains `pending` and does not block P12 or `P_DB_INDEX`.
