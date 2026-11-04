# Status

Version: v0 (in development). Updated: 2026-11-04.

| Step | What | State |
|---|---|---|
| 1 | Skeleton: install.sh, doctor, leak check + tests, licence, disclaimer, README | done |
| 2 | `legal-workflow`: router, profile, matters, working norms | done (branch `phase-1/legal-workflow`) |
| 3 | `legal-contracts` (draft / audit / redline, MD-RO-EU) | done (branch `phase-1/legal-contracts` on top of step 2; merge to `main` only after the owner's «да») |
| 4 | `legal-research` (question with citations, current-version check) | next |
| 5 | `legal-workflow-setup` wizard + `legal-workflow-update` | — |
| 6 | modules `legal-privacy`, `legal-consumer` | — |
| 7 | module `legal-trademark` | — |
| 8 | module `legal-employment` | — |
| 9 | `legal-watch`: niche → law catalog, law library, monitoring, contract re-review | — |
| 10 | end-to-end check, cross-model review, v1.0.0 | — |
| 11 | public GitHub repository and first push (owner's «да» first) | — |

Checks: `python3 tools/check.py` · `python3 -m unittest discover -s tools/tests` ·
`.venv/bin/python -m unittest discover -s skills/<skill>/tests` (the pre-commit hook runs all of them; contract tools
need `.venv` from `./install.sh`).

Contracts later steps must follow (in `skills/legal-workflow/references/`): `profile.md` (profile layout,
`modules.json`, setup steps written only via `legal_profile.py step set`), `matters.md` (matter folder,
`input/` · `output/` deliverables · `work/` working files, `intake.json` core + `module_data` written via
`matter update`, `log.md`, handoff to a module), `norms.md`,
`law-check.md` (law check and the shared `source-register.json`, task_id `<matter-id>@<date>`, checked by
`scripts/check_register.py`), `sources.md`, `jurisdiction.md`. Document tools (DOCX, Word redline, Romanian style
and structure checks, model library) live in `legal-contracts`; other modules reuse them by path.

Minor, later: `check_register.py` stops at the first malformed source or finding (one `try`); per-item checks
would list all errors at once.
Open for step 4: `legal-research` builds on `law-check.md` (do not fork it); current-version check of a rule.
Open for step 5: script commands `profile init` (folder + config.json) and `modules set`, so the wizard never
writes these files by hand. Rollout: until step 5 do not install the engine next to a personal contracts skill with
overlapping trigger phrases.
Open for step 6: privacy substance (checklist for notices, DPA, cookies, transfers; Romanian privacy templates)
comes with `legal-privacy`; it reuses the contract tools and model cards M06–M10.
