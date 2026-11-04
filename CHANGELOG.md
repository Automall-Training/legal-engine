# Changelog

## Unreleased

- `legal-workflow` skill: entry point and router by module (states core / on / off / unset / not-installed),
  profile lookup via `~/.config/legal-engine/config.json` (a profile inside the engine is refused), only the
  missing setup steps, matters `matters/YYYY-MM-DD-slug/` with an append-only `matters/log.md`, approval
  boundaries, working norms (`references/norms.md`). Script `legal_profile.py` (status, module, step set,
  matter new / log / show / list) with tests; `doctor.py` reuses its profile lookup; the hook runs skill tests.
- Repository skeleton: `install.sh`, `tools/doctor.py` (machine check), `tools/check.py` (leak check of the
  public repo, also inside .docx), tests, licence, disclaimer.
