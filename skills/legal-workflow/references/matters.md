# Matters

A matter is one piece of legal work: one contract, one question, one policy, one re-review. Everything of a
matter stays in its folder inside the profile, never inside the engine.

## Layout

```text
<profile>/matters/
  log.md                       append-only journal of all matters
  YYYY-MM-DD-slug/             one matter (a clash gets -02, -03, …)
    intake.json                created by legal_profile.py
    source-register.json       law the module cites (law-check.md); older checks: source-register.<date>.json
    input/                     files the user gave (originals, never edited)
    output/                    files the engine produced (drafts, clean and tracked DOCX, reports)
```

`slug` is short lowercase latin words joined by `-` (for example `nda-supplier`, `privacy-policy-site`).

## intake.json

Two owners, so a module never breaks another:

- **generic core**, written by `matter new`: `schema_version`, `task_id` (= matter id), `module`, `title`,
  `created`, `represented_party`, `communication_language`, `document_language`, `input_files`, `unknowns`;
- **`module_data`**: an object owned by the matter's module (for contracts: action, document type, parties,
  governing law, forum, dates, agreed constraints, …). Other modules read it, never write it.

Nobody deletes core fields. A module writes its answers only through the script, which keeps the identity fields
(`schema_version`, `task_id`, `module`, `title`, `created`), replaces the editable core fields it is given and
merges the keys of `module_data`:

```bash
python3 <skill>/scripts/legal_profile.py matter update <matter-id> --data '{"represented_party": "…", "module_data": {"action": "audit"}}'
python3 <skill>/scripts/legal_profile.py matter update <matter-id> --data @/tmp/intake-update.json   # long texts: a temporary JSON file
```

## log.md

One row per event, newest last; rows are never edited or removed. The last row other than `note` is the
status of the matter.

```markdown
| Date | Matter | Module | Event | Note |
|---|---|---|---|---|
| 2026-11-04 | 2026-11-04-nda-supplier | contracts | opened | NDA with a supplier |
| 2026-11-04 | 2026-11-04-nda-supplier | contracts | waiting | asked for the supplier's legal form |
```

Events: `opened` (written only by `matter new`), `waiting` (needs the user), `resumed`, `done`, `dropped`,
`note`. Write and read them only through the script; modules never parse `log.md` themselves:

```bash
python3 <skill>/scripts/legal_profile.py matter new --slug nda-supplier --title "NDA with a supplier" --module contracts
python3 <skill>/scripts/legal_profile.py matter log 2026-11-04-nda-supplier --event done --note "clean and tracked DOCX delivered"
python3 <skill>/scripts/legal_profile.py matter show 2026-11-04-nda-supplier
python3 <skill>/scripts/legal_profile.py matter list --open
```

Notes carry no personal data beyond what the user already put into the matter; never IDs, bank accounts or
health data.

## Handoff to a module

`legal-workflow` gives the module: the matter id and path, the user's request word for word, the profile path,
the module id, and the language pair from `context/language.md`. The module then:

- keeps the user's files in `input/` unchanged and writes everything it produces to `output/`;
- fills its part of `intake.json` (`module_data`) and the core fields it learns, through `matter update`;
- keeps law it cites in `source-register.json` in the matter folder, in the one shared format of
  `law-check.md` (template `assets/source-register.json`, checked by `scripts/check_register.py`);
- logs `waiting` / `done` / `dropped` through the script and reports working links to `output/` files;
- follows `norms.md` by reference and the approval boundaries of `SKILL.md`; it never copies them.
