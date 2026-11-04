# Matters

A matter is one piece of legal work: one contract, one question, one policy, one re-review. Everything of a
matter stays in its folder inside the profile, never inside the engine.

## Layout

```text
<profile>/matters/
  log.md                       append-only journal of all matters
  YYYY-MM-DD-slug/             one matter (a clash gets -02, -03, …)
    intake.json                created by legal_profile.py
    source-register.json       created by the module that cites law
    input/                     files the user gave (originals, never edited)
    output/                    files the engine produced (drafts, clean and tracked DOCX, reports)
```

`slug` is short lowercase latin words joined by `-` (for example `nda-supplier`, `privacy-policy-site`).

## intake.json

The intake fields of the contract module (`action`, `document_type`, `commercial_goal`, `represented_party`,
`parties`, `confirmed_facts`, `assumptions`, `unknowns`, `governing_law`, `forum`, `cross_border_factors`,
dates, `agreed_constraints`, `communication_language`, `document_language`, `input_files`) plus
`schema_version`, `task_id` (= matter id), `module`, `title`, `created`. Modules fill it; nobody deletes fields.

## log.md

One row per event, newest last; rows are never edited or removed. The last row other than `note` is the
status of the matter.

```markdown
| Date | Matter | Module | Event | Note |
|---|---|---|---|---|
| 2026-11-04 | 2026-11-04-nda-supplier | contracts | opened | NDA with a supplier |
| 2026-11-04 | 2026-11-04-nda-supplier | contracts | waiting | asked for the supplier's legal form |
```

Events: `opened`, `waiting` (needs the user), `resumed`, `done`, `dropped`, `note`.
Write them only through the script:

```bash
python3 <skill>/scripts/legal_profile.py matter new --slug nda-supplier --title "NDA with a supplier" --module contracts
python3 <skill>/scripts/legal_profile.py matter log 2026-11-04-nda-supplier --event done --note "clean and tracked DOCX delivered"
python3 <skill>/scripts/legal_profile.py matter list --open
```

Notes carry no personal data beyond what the user already put into the matter; never IDs, bank accounts or
health data.
