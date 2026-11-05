---
name: legal-research
description: Legal question module of the legal engine (Moldova, Romania, EU) - answers "can I…", "is it legal…", "which rule applies", deadlines, sanctions and authorities with quotes from the official text in the version in force today, a lawful path first, a weighed risk and an honest "not verified" list; and checks whether an act is the current version (consolidations, amending acts, delayed entry, secondary acts, court decisions, repeal). Works inside a matter opened by legal-workflow. Use for "можно ли законно", "какой закон применяется", "какой штраф", "это действующая редакция?", "проверь редакцию закона", "e legal?", "ce lege se aplică", "este în vigoare?", "is this the current version of the law", "what does the law say".
---

# Legal Research

Resolve this skill's directory (`<skill-dir>` below); the entry skill is `<skill-dir>/../legal-workflow/`
(`<legal-workflow>` below). The law method (`law-check.md`, `sources.md`, `jurisdiction.md`), the working norms
and the approval boundaries live there and are followed by reference, never copied. The script is stdlib only.

## Before anything

1. **Handoff.** Work needs what `<legal-workflow>/references/matters.md` § "Handoff to a module" lists. Called
   directly without it → load `<legal-workflow>/SKILL.md`, follow its Start, then come back. A quick factual reply
   needs no matter; it still names its sources and what was not verified.
2. **Scope.** A pure question inside another module's area (a contract, privacy, consumer sales, trademarks,
   employment) belongs to that module; if the module is off, go back to the router (`<legal-workflow>/SKILL.md`,
   Start step 6: say so and offer to turn it on), never answer it here. The only exception is the one the router
   documents (a personal-data breach). This module answers general questions and runs version checks for every
   module that asks for one.
3. **Norms.** Read `<legal-workflow>/references/norms.md` once per session, and [traps.md](references/traps.md)
   before the first check.

## Route

1. **Question** — restate it (who, what, where, on what date) and record it with the facts:
   `python3 <legal-workflow>/scripts/legal_profile.py matter update <id> --data @<matter>/work/intake-update.json`
   (shape: [templates/module-data.json](templates/module-data.json); `unknowns` is a core field). Ask only a
   material unknown that both branches of the answer cannot cover; one question, options, recommended first.
2. **Regime** — `<legal-workflow>/references/jurisdiction.md`. Several jurisdictions are answered side by side,
   each with its own rules and sources.
3. **Find the rules** — `<legal-workflow>/references/sources.md` and [access.md](references/access.md). Search by
   subject, without the user's names, figures or confidential text.
4. **Current-version check** — [version-check.md](references/version-check.md) for every act a material
   conclusion rests on: one card per act in `<matter>/work/versions/`, saved texts in `<matter>/work/sources/`.
   `held_version` comes from `watch show` when the act is watched; a card from today about the whole act also
   updates the law library (`watch record`, `<skill-dir>/../legal-watch/references/library.md`).
   ```bash
   python3 <skill-dir>/scripts/check_version.py <matter>/work/versions/<act-id>.json --root <matter>
   ```
5. **Register** — `<legal-workflow>/references/law-check.md`: each cited provision is a source in
   `<matter>/source-register.json`, its checks filled from the card; then
   ```bash
   python3 <legal-workflow>/scripts/check_register.py <matter>/source-register.json --task-id <matter-id>@<today's check date>
   ```
6. **Answer** — [answer.md](references/answer.md) with the [shell](templates/answer.md), in
   `<matter>/output/answer.md`. Every conclusion labelled; the lawful path first; the risk weighed; sources and
   "not verified" never omitted.
7. **Close** — `matter log <id> --event done --note "answer delivered"` or `waiting` with the question; give a
   working link to `output/answer.md`. A version check alone (`action: version_check`) delivers the card result
   and the sources block.

Another module that needs a version check reads [version-check.md](references/version-check.md) and runs the
same script on its own matter; it does not copy the procedure.

## Never

- A conclusion "the rule is in force" from memory, a cache, a snippet, an unofficial site or an old archived copy.
- A future version, a draft or a guideline presented as the law.
- An invented article number, date, version or quote: not found is written as not found.
- "No changes" where a source failed: that is `not_verified` with a working conclusion.
- Personal data or commercial details of the user in a search query.
- Signing, sending, publishing or filing anything (`<legal-workflow>/SKILL.md`, approval boundaries).
