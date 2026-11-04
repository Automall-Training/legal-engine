---
name: legal-trademark
description: Trademarks module of the legal engine (Moldova, Romania, EU) for any business with its own name, brand or logo - checking a new name against earlier rights, choosing where and how to file (AGEPI, OSIM, EUIPO, Madrid) at the lowest cost for the market, the portfolio and its deadlines (opposition windows, certificate fee, renewal, five years of use), office letters, oppositions, someone copying the brand, a claim against the user's brand, licences between the owner and the firms, all checked against the official text on the task date. Works inside a matter opened by legal-workflow, only when the module is on. Use for "торговая марка", "зарегистрировать бренд", "проверь название", "нас копируют", "претензия по марке", "продление марки", "marcă", "înregistrare marcă", "opoziție", "OSIM", "AGEPI", "EUIPO", "trademark", "brand name check", "cease and desist".
---

# Legal Trademark

Resolve this skill's directory (`<skill-dir>` below); the entry skill is `<skill-dir>/../legal-workflow/`
(`<legal-workflow>` below) and the contract tools are in `<skill-dir>/../legal-contracts/` (`<legal-contracts>`).
The law method, the working norms and the approval boundaries live in `<legal-workflow>` and are followed by
reference, never copied. This module decides **how the user can use and protect a sign**; letters and licences
are drafted with the contract tools.

## Before anything

1. **Module on?** `python3 <legal-workflow>/scripts/legal_profile.py module trademark` → `on` continues. `off` →
   say the module is off and that the setup wizard (step `modules`) or `legal-workflow-update` turns it on; do
   nothing else in this area. `unset` → run the wizard's step `modules`.
2. **Handoff.** Work needs what `<legal-workflow>/references/matters.md` § "Handoff to a module" lists. Called
   directly without it → load `<legal-workflow>/SKILL.md`, follow its Start, then come back.
3. **Deadline first.** A letter from an office, a warning letter or an opposition may run a term: read the date
   received and the term before anything else, and put an urgent one (under 14 days) at the top of the answer.
4. **Norms.** Read `<legal-workflow>/references/norms.md` once per session and [law-map.md](references/law-map.md)
   before the first conclusion.

## Route

1. **Facts** — the sign (word, logo, both), what it is used for, which firm or person uses and owns it, the
   territories now and planned, earlier filings, the documents received. Record them:
   `python3 <legal-workflow>/scripts/legal_profile.py matter update <id> --data @<matter>/work/intake-update.json`
   (shape: [templates/module-data.json](templates/module-data.json)).
2. **Procedure** — [procedures.md](references/procedures.md): 1 name check · 2 filing strategy · 3 portfolio and
   deadlines · 4 office letter · 5 opposition · 6 someone uses our sign · 7 a claim against us · 8 licence and
   ownership.
3. **Configuration** — for a name, a filing or a conflict, two to four options with cost, residual risk and
   verdict, the cheapest lawful one first ([filing-strategy.md](references/filing-strategy.md);
   `norms.md` §15). One recommendation.
4. **Deadlines** — `python3 <skill-dir>/scripts/tm_deadlines.py portfolio --file <profile>/trademarks/portfolio.json`
   (or `compute --rule <id> --date <event>`); every date with its rule, article and "check on the task date".
5. **Law check** — every material conclusion, term and fee rests on the official text or the office's current
   list read on the task date: `<legal-workflow>/references/law-check.md`, the source register and
   `check_register.py`, and the current-version card of `<skill-dir>/../legal-research/references/version-check.md`.
6. **Documents** — letters, briefs and replies as short texts; a licence or an assignment through
   `<legal-contracts>` model card M05 (`<legal-contracts>/references/models/05-licenta.ro.md`) and its route
   steps 6–9 in the same matter.
7. **Deliver** — deliverables in `output/`; a short report: urgent deadlines first, the options table with the
   recommendation, sources with dates, not verified; log `waiting` or `done` through `legal_profile.py matter log`.

## Rules of this module

- **Use is not registration.** A name may be used without a registration; the real question is the earlier
  rights of others, weighed per territory and goods. A registration is protection, not a permission.
- **No "available".** The verdict is the scale of `norms.md` §5 with the sources and the date checked. Never
  "available", "free", "guaranteed to register".
- **An application is not a registration**: no `®`, no claim of registered rights; rights "subject to
  registration" as the law map says.
- **Proportionate enforcement.** The ladder of procedure 6, one rung at a time; no threats, no money demands in
  a first letter; the cheapest step that can work first.
- **No invented numbers.** Office numbers, dates, classes and fees come from documents or the office's current
  list; unknown → `null` and an open question.
- **Data of others.** Names of private individuals who file or infringe stay out of notes and searches; office,
  number and class are enough.
- **Never** file, pay, oppose, send a letter or report to a platform: the engine prepares; the user or their
  representative acts (`<legal-workflow>/SKILL.md`, approval boundaries).

Resources: [sources](references/sources.md), [examples](examples/requests.md),
[behaviour scenarios](tests/scenarios.md) (test inputs, not law).
