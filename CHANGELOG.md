# Changelog

## Unreleased

- `legal-privacy` module: GDPR, Moldovan Law 195/2024, Romanian Law 190/2018. Six procedures (website or form,
  processor or DPA, transfer abroad incl. a non-EU controller, DPIA screening, data request, breach with the
  72-hour deadline first), the minimum content of each document with model cards M06–M10, law map as navigation.
  The router sends a data breach to it whatever the module state.
- `legal-consumer` module: sales to consumers online, checkpoints C1–C14 for RO / EU (information, order button,
  withdrawal and its digital-content exceptions, online withdrawal function, conformity, price reductions, unfair
  terms, complaints and ADR) and the Moldovan part, never filled from the Romanian column.
- `tools/tests/test_skills.py`: consistency of every skill (frontmatter, relative links, JSON, module templates
  accepted by `matter update`, optional modules check their switch).
- `legal-workflow-setup` wizard: creates the private profile and fills it one question at a time (firms, whom they
  sell to → suggested modules, modules on/off, languages, side and risk threshold, own samples and contracts with
  house style, local tools after one approval); quick or full depth, resumes from `integration-status.md`, never
  overwrites an answer silently; law-library steps wait for `legal-watch`. Context file templates.
- `legal-workflow-update` skill (human-invoked only): changes the profile after feedback, after a "yes" to the exact
  change; engine-level problems become a drafted issue, never an edit of the engine folder; migration rules.
- `legal_profile.py`: `profile init` (folders and `config.json`, `--switch` to repoint, `--create` for a configured
  folder that is missing; refuses the home folder and any folder inside or around the engine), `modules set` (a
  skipped modules step reads as all off), atomic writes for every profile file, `where` reports the engine folder. The router
  checks that a module is installed before running the wizard for it.
- `legal-research` skill: legal question with quotes from the version in force (lawful path first, labelled
  conclusions, weighed risk, sources and "not verified" blocks) and the current-version check of an act in seven
  points (consolidation, amendments incl. the official journal, delayed entry, secondary acts, case law, repeal,
  status of changes), one version card per act. `check_version.py` checks the card: evidence opened today from an
  official source, archived copies never prove the latest version, future versions and drafts never in force,
  optional quote-in-saved-text check (HTML and PDF artefacts tolerated). Access routes for MD / RO / EU sources,
  traps, answer shell. `law-check.md` and `legal-contracts` point to it instead of copying it.
- `legal-contracts` skill: draft, audit, edit and adapt contracts and commercial documents (MD / RO / EU) inside a
  matter: intake into `module_data`, law check with the shared source register, Romanian model library with official
  links (originals are downloaded on demand, not shipped), templates, audit report shell, delivery checklist.
  Scripts: `build_docx.py`, `docx_redline.py` (real Word tracked changes + clean copy, accept = clean,
  reject = original), `check_ro_style.py`, `check_structure.py`; they re-run in the engine's `.venv` when needed and
  refuse to write inside the engine folder. Tests with the synthetic redline example.
- `legal-workflow`: shared law check (`law-check.md`, `sources.md`, `jurisdiction.md`), source register template and
  `check_register.py`, command `matter update` (modules fill `intake.json` without hand edits).
- Pre-commit hook runs skill tests with `.venv` when present.
- `legal-workflow` skill: entry point and router by module (states core / on / off / unset / not-installed),
  profile lookup via `~/.config/legal-engine/config.json` (a profile inside the engine is refused), only the
  missing setup steps, matters `matters/YYYY-MM-DD-slug/` with an append-only `matters/log.md`, approval
  boundaries, working norms (`references/norms.md`). Script `legal_profile.py` (status, module, step set,
  matter new / log / show / list) with tests; `doctor.py` reuses its profile lookup; the hook runs skill tests.
- Repository skeleton: `install.sh`, `tools/doctor.py` (machine check), `tools/check.py` (leak check of the
  public repo, also inside .docx), tests, licence, disclaimer.
