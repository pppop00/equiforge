---
schema_version: 1
name: single_prompt_run
description: One-prompt end-to-end procedure. Slash-command equivalent of "run the whole equiforge workflow on this prompt".
when_to_use: User gives a single research prompt (e.g. "研究一下苹果", "research Apple", "build cards for Tencent")
requires_toolsets: ["research", "photo", "audit", "db", "web", "io"]
---

# /single_prompt_run

The ten-step procedure the orchestrator walks for any one prompt.

```
1. Bootstrap          → tools/io/run_dir.py + write meta/system_prompt.frozen.txt + meta/submodule_shas.json
2. P0_intent          → agents/intent_resolver.md
3. P0_lang            → agents/language_gate.md (sticky-fast-path through USER.md)
4. P0_sec_email       → agents/sec_email_gate.md (only if listing=US, mode=A, no sticky)
5. P0_palette         → agents/palette_gate.md (sticky-fast-path through USER.md)
6. P0M_meta + P0_DB_PRECHECK → tools/research/validate_workflow_meta.py + tools/db/queries.py
7. ER pipeline        → see skills/er_phase_runner.md (P1..P6)
8. EP pipeline        → see skills/ep_pipeline_runner.md (P7..P11)
9. P12 final audit    → agents/post_card_auditor.md (4 layers)
10. P_DB_INDEX        → tools/db/index_run.py
```

After step 10, return to the user (in `report_language`):
- absolute path to `output/{Company}_{Date}_{RunID}/`
- list of 6 PNG paths
- HTML report path
- `validation/QA_REPORT.md` summary verdict
- count of new DB rows + any peer-divergence flags

## Failure handling at this layer

- If P0 gates produce no answer after one re-ask, halt and tell the user "I cannot proceed without <gate>; reply with one of <values>" — do not spin.
- If P12 fails, do not run P_DB_INDEX. Surface paths + ask which upstream phase to re-run.
- If P_DB_INDEX fails, the run is still successful from the user's perspective — research + cards + QA are all on disk. Surface `db_export/index_error.json` and recommend `python tools/db/index_run.py --run-dir <path>` for manual retry.

## Resume

If the user invokes this on an existing run dir (`equiforge run --resume <run_id>`), read `meta/run.jsonl` and skip phases whose `phase_exit` event already exists with valid output artifacts.
