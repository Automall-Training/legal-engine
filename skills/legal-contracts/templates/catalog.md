# Templates

Every template needs the facts, the applicable law and a fresh law check. None is a mandatory or approved form and
none is ready to sign. Editorial instructions never stay in the final text. Empty fields stay only in a document
clearly marked as a draft.

First pick a [structure source](../references/models/catalog.md) (or the user's own sample from
`<profile>/templates/`). The templates below are this engine's own modules, not copies of published models. The
library marks official SCCs separately: they have special limits on changing the text.

- [commercial-ro.md](commercial-ro.md) — services contract and modules for NDA, supply, licence and amendment.
- [transaction-pack.ro.md](transaction-pack.ro.md) — commercial sheet, specification and payment schedule.
- [audit-report.md](audit-report.md) — audit report shell; write it in the conversation language.
- [module-data.json](module-data.json) — this module's part of `intake.json` (written with `matter update`).
- [document.json](document.json) — neutral technical base of a DOCX for `build_docx.py`.
- The source register template is shared: `legal-workflow/assets/source-register.json`.

Use: pick the modules you need → drop what does not apply → check what is mandatory and sufficient → fill in the
agreed terms → check language and terms → build the DOCX → compare visually. Never include the whole catalog by
default.
