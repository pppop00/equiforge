---
description: Draft a new INCIDENTS.md entry from a one-line user description plus the latest run.jsonl. The user reviews and confirms before the entry is appended.
allowed-tools: Bash, Read, Edit, Write
argument-hint: <one-line description of what went wrong>
---

# /log-incident

A new failure mode just happened (or just got fixed). Capture it as an `INCIDENTS.md` entry so the next run does not repeat it.

## Procedure

1. **Parse the user's description.** It comes in as `$ARGUMENTS`. Treat it as a short summary (the *what*); you will write the *why*, *rule*, and *detection* yourself from evidence.

2. **Locate the latest run.** Run:
   ```bash
   python3 tools/io/log_incident.py --collect
   ```
   This prints JSON with the most recent run dir and a digest of `meta/run.jsonl` (last ~50 events), `meta/gates.json`, the resolved `meta/run.json`, and any phase output that landed under `validation/` or `research/structure_conformance.json`. If the user's description references a specific run, they may pass `--run-dir <path>` instead — re-run with that flag.

3. **Read INCIDENTS.md.** Find the next free `I-NNN` id (max existing + 1). Re-read existing entries to make sure this is genuinely new and not a recurrence of an existing one. If it is a recurrence, **do not create a new entry** — instead, surface the matching existing entry to the user and ask whether they want to *amend* it (add a new "Date observed" line) or whether their incident is genuinely a new variant.

4. **Draft a candidate entry.** Match the format of existing entries exactly:
   - `## I-NNN — <short title>`
   - `**Date observed:**` (today, YYYY-MM-DD)
   - `**Phase:**` (the phase id from `workflow_meta.json` where the failure surfaced)
   - `**What happened:**` (specific, with paths from the digest — not generic)
   - `**Root cause:**` (the assumption or shortcut that produced the failure)
   - `**Rule (load-bearing):**` (the contract that prevents recurrence — must be enforceable, not advice)
   - `**Detection:**` (which tool or test catches it; if none exists, propose one and flag it as a follow-up)
   - `**Related contract:**` (which existing files must be cross-referenced)

5. **Show the draft to the user.** Print it back, ask "ready to append? (y/n)". Do **not** write to `INCIDENTS.md` until the user replies `y` or equivalent.

6. **On confirm, append.** Use Edit to insert the new entry **before** the trailing `## How this file is used` section. Preserve the `---` separator above each entry. Do not reorder existing entries.

7. **Verify.** Read `INCIDENTS.md` back and show the user the diff (just the inserted block). Remind them that future sessions will see this entry as part of the frozen system prompt.

## What you must NOT do

- Do not invent details. If a piece of information is not in the run digest or the user's description, leave it as `<unknown — to be filled in by user>` rather than fabricating.
- Do not append without explicit user confirmation. The whole point of this command is human-in-the-loop curation.
- Do not delete or edit existing entries. INCIDENTS.md is append-only; corrections happen through new entries that supersede old ones with a back-link.
- Do not write entries for warn-level findings. INCIDENTS is for *load-bearing* failure modes — things worth permanently re-reading every run. A one-time edge case in a single run is not an incident.
