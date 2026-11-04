# Intake

Take the facts from the request, the correspondence and every attachment. Keep apart confirmed facts, what the
contract states, assumptions and unknowns. Do not ask again for what the profile or the matter already holds.

## Where the answers go

`legal_profile.py matter new` writes the **core** of `intake.json` (see `legal-workflow/references/matters.md`).
This module fills the core fields it learns and owns **`module_data`**, shaped like
[`../templates/module-data.json`](../templates/module-data.json):

| Field | What to establish |
| --- | --- |
| `represented_party` (core) | Whose side we hold. Default: the user's firm from `context/side-and-risk.md`; if that step was skipped or several firms fit, ask once |
| `communication_language`, `document_language` (core) | Separately; from `context/language.md`, an explicit instruction wins. `language_reason` says why |
| `input_files` (core) | Each file in `input/` with its SHA-256, version, signed or not, old revisions, annexes, reading quality |
| `unknowns` (core) | Material unknowns with the fact that would decide them |
| `action` | `draft`, `audit`, `edit` or `adapt`; the files expected |
| `document_type`, `commercial_goal` | Kind of document, economic result, obligations |
| `parties` | Countries, B2B/B2C status, place of business and performance, authority to sign |
| `confirmed_facts`, `assumptions` | Kept apart; an assumption never changes an agreed term |
| `governing_law`, `forum`, `cross_border_factors` | Existing clauses, court, arbitration and its seat, enforcement; method in `legal-workflow/references/jurisdiction.md` |
| `execution_date`, `performance_period`, `analysis_date`, `checked_at` | Today's date from the clock, analysis date, signing, performance, renewal |
| `agreed_constraints` | What is agreed and must not change; depth and priorities of the work |
| `structure_sources` | Model id (`M01`…) and source sections used, see `models/catalog.md` |

"As of today" means the date of the system clock, not the date this engine was written. Without an analysis date
the analysis is as of today; for a past disputed event, settle its date before a categorical conclusion.

## Profile files this module reads

- `context/company.md` — the user's firms (only the confirmed details; never guess IDNO, CUI, address or accounts);
- `context/side-and-risk.md` — the side and the "decide myself / ask" threshold (`norms.md` §6 by default);
- `context/language.md` — the language pair;
- `context/house-style.md` (optional) — the user's placeholders, preferred clauses, default court or arbitration;
  a preference is applied only after the law check allows it for this deal;
- `templates/` (optional) — the user's own samples: a structure source like a model card, never proof of law.

## Unknowns

Missing party details usually allow a draft with `[DE COMPLETAT: …]` fields. An unknown consumer status, event date,
processing purpose or territorial link can block a specific conclusion: give conditional options and name the fact
that picks one.

For a signed contract keep apart validity at signing, its effects now and a future amendment. Never rewrite a signed
original as if it were the same historical deal. Never ask for data subjects' names when categories are enough.
