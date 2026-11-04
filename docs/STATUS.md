# Status

Version: v0 (in development). Updated: 2026-11-04.

| Step | What | State |
|---|---|---|
| 1 | Skeleton: install.sh, doctor, leak check + tests, licence, disclaimer, README | done |
| 2 | `legal-workflow`: router, profile, matters, working norms | done (branch `phase-1/legal-workflow`, awaiting owner's «да») |
| 3 | `legal-contracts` (draft / audit / redline, MD-RO-EU) | next |
| 4 | `legal-research` (question with citations, current-version check) | — |
| 5 | `legal-workflow-setup` wizard + `legal-workflow-update` | — |
| 6 | modules `legal-privacy`, `legal-consumer` | — |
| 7 | module `legal-trademark` | — |
| 8 | module `legal-employment` | — |
| 9 | `legal-watch`: niche → law catalog, law library, monitoring, contract re-review | — |
| 10 | end-to-end check, cross-model review, v1.0.0 | — |
| 11 | public GitHub repository and first push (owner's «да» first) | — |

Checks: `python3 -m unittest discover -s tools/tests` · `python3 -m unittest discover -s skills/legal-workflow/tests` ·
`python3 tools/check.py` (the pre-commit hook runs all three).

Contracts later steps must follow (in `skills/legal-workflow/references/`): `profile.md` (profile layout,
`modules.json`, setup steps written only via `legal_profile.py step set`), `matters.md` (matter folder,
`intake.json` core + `module_data`, `log.md`, handoff to a module), `norms.md`.
Open for step 3: one shared `source-register.json` format (from legal-md-ro).
