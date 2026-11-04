# Profile contract

The profile holds everything that belongs to one user. It lives **outside the engine folder** (the script
refuses a profile inside it). The engine never commits, uploads or shares it.

## Where it is

`~/.config/legal-engine/config.json` (another file: environment variable `LEGAL_ENGINE_CONFIG`):

```json
{"profile_dir": "~/legal-profile"}
```

`profile_dir` is absolute or starts with `~`. No config means the default `~/legal-profile`.
A broken config is an error to show the user, never a reason to guess another folder.

## Layout

```text
<profile>/
  context/
    company.md            firms: country, legal form, VAT, activity, B2B/B2C, website
    side-and-risk.md      whose side we hold, threshold "decide myself / ask" (default: norms.md §6)
    language.md           language of conversation and language of documents, separately
    house-style.md        own placeholders, preferred clauses, default court/arbitration, user decisions
    integration-status.md setup steps (table below)
  modules.json            optional modules on/off
  templates/              the user's own sample documents (optional)
  matters/                see matters.md
  laws/                   watchlist.yaml, texts/, runs/ (legal-watch)
  contracts/              the user's contracts in force + index/ (legal-watch)
```

## modules.json

```json
{"schema_version": 1, "privacy": true, "consumer": false, "trademark": false, "employment": true}
```

Only the optional modules from `assets/modules.json` are allowed; a missing key means off. Core modules
(contracts, research, watch) are always on and are not listed.

## Setup steps (`context/integration-status.md`)

The wizard keeps one table row per step; a missing row means `pending`.

```markdown
| Step | Status | Updated | Note |
|---|---|---|---|
| firms | done | 2026-11-04 | |
| audience | skipped | 2026-11-04 | |
```

Status is `done`, `skipped` or `pending`. Step ids and wizard questions:

| Step id | Wizard question | File it writes |
|---|---|---|
| firms | 1. your firms | `context/company.md` |
| audience | 2. whom you sell to → suggested modules | `context/company.md` |
| modules | 3. confirm modules | `modules.json` |
| language | 4. languages | `context/language.md` |
| side-risk | 5. side and risk threshold | `context/side-and-risk.md` |
| niches | 6. business niches and law categories | `laws/watchlist.yaml` |
| laws | 7. acts to download, frequency, engine | `laws/watchlist.yaml` |
| documents | 8. own samples and contracts in force | `templates/`, `contracts/` |
| tools | 9. local tools | — |
| first-run | 10. first download and trial monitoring | `laws/runs/` |

Every module needs `firms`, `modules`, `language`, `side-risk` (`base_needs`); a module may need more
(`legal-watch`: `niches`, `laws`). `skipped` counts as satisfied. A step marked `done` whose file is missing
counts as `pending`. `legal_profile.py status --module <id>` returns exactly the missing steps.
