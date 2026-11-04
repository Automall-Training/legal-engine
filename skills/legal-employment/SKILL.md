---
name: legal-employment
description: Employment module of the legal engine (Moldova, Romania, EU) for any business with staff or plans to hire - choosing how to engage a person (employment contract full or part time, fixed term, remote, or a civil contract with a self-employed person) at the lowest compliance cost and risk, hiring documents, amendments (salary, position, hours, place, remote work), ending a contract (agreement, resignation, end of term, dismissal with its procedure), internal rules, a labour inspection or an employee's claim, workers across the Moldova-EU border, all checked against the Labour Code in force on the task date. Works inside a matter opened by legal-workflow, only when the module is on. Use for "принять на работу", "трудовой договор", "допсоглашение", "уволить сотрудника", "по соглашению сторон", "сотрудник на удалёнке", "договор с ИП вместо трудового", "angajare", "contract individual de muncă", "act adițional", "concediere", "demisie", "REVISAL", "telemuncă", "hire", "employment contract", "dismissal".
---

# Legal Employment

Resolve this skill's directory (`<skill-dir>` below); the entry skill is `<skill-dir>/../legal-workflow/`
(`<legal-workflow>` below) and the contract tools are in `<skill-dir>/../legal-contracts/` (`<legal-contracts>`).
The law method, the working norms and the approval boundaries live in `<legal-workflow>` and are followed by
reference, never copied. This module decides **how the user can engage, change and end work with a person
lawfully and at the lowest cost**; the DOCX, the Romanian style check and the tracked changes are made with the
contract tools.

## Before anything

1. **Module on?** `python3 <legal-workflow>/scripts/legal_profile.py module employment` → `on` continues. `off` →
   say the module is off and that the setup wizard (step `modules`) or `legal-workflow-update` turns it on; do
   nothing else in this area. `unset` → run the wizard's step `modules`.
2. **Handoff.** Work needs what `<legal-workflow>/references/matters.md` § "Handoff to a module" lists. Called
   directly without it → load `<legal-workflow>/SKILL.md`, follow its Start, then come back.
3. **Deadline first.** A dismissal, a resignation, an inspection or a claim may run a term (notice, a disciplinary
   limit, a court limit): read the dates and put an urgent one at the top of the answer.
4. **Norms.** Read `<legal-workflow>/references/norms.md` once per session and [law-map.md](references/law-map.md)
   before the first conclusion.

## Route

1. **Facts** — the employer (the profile's `context/company.md`), the person (role, country of residence, where
   they actually work, citizenship only when the right to work is in question), hours, pay, start date, how work
   is organised (schedule, place, tools, who gives instructions), what already exists in writing. Record them:
   `python3 <legal-workflow>/scripts/legal_profile.py matter update <id> --data @<matter>/work/intake-update.json`
   (shape: [templates/module-data.json](templates/module-data.json)). Personal data of the person stays in
   `<matter>/input/` and in the documents; notes use the role, not the name.
2. **Regime** — the law of the country where the person habitually works protects them whatever the contract
   says (Rome I art. 8 before EU courts; the Moldovan conflict rule before Moldovan courts, *reported*;
   `<legal-workflow>/references/jurisdiction.md`). Social security and tax follow their own rules
   ([law-map.md](references/law-map.md), cross-border).
3. **Configuration** — for "how do I engage / change / end", compare two to four options with what each needs,
   cost, residual risk and verdict, the simplest lawful one first ([configuration.md](references/configuration.md);
   `norms.md` §15). One recommendation.
4. **Procedure** — [procedures.md](references/procedures.md): 1 hiring · 2 amendment · 3 ending · 4 internal
   rules · 5 contractor or employee · 6 inspection or claim · 7 work across borders.
5. **Law check** — every material conclusion, term and amount (minimum wage, contributions, notice, severance)
   rests on the official text read on the task date: `<legal-workflow>/references/law-check.md`, the source
   register and `check_register.py`, and the current-version card of
   `<skill-dir>/../legal-research/references/version-check.md`. Amounts change every year: never from memory.
6. **Documents** — structure and required content from [documents.md](references/documents.md); drafting,
   DOCX, style check and tracked changes through `<legal-contracts>` route steps 6–9 in the same matter. An
   existing contract is amended with an addendum or real tracked changes, never silently rebuilt.
7. **Deliver** — deliverables in `output/`; a short report: urgent dates first, the options table and the
   recommendation, what the law requires and what is only recommended, sources with dates, not verified, the
   steps the user takes (sign, register, pay, hand over) in order; log `waiting` or `done` through
   `legal_profile.py matter log`.

## Rules of this module

- **A lawful way to work first.** The question is how the business can get the work done and how the person can
  be engaged, changed or let go lawfully, not whether. A real prohibition (a protected period, a missing ground)
  is named with its rule and the nearest lawful alternative (`norms.md` §2, §15).
- **Required only what the law requires.** Documents, orders, registers and policies that the law does not
  require for this employer are `recomandare`, and are added only when they remove a real risk. A form the law
  makes optional is offered as optional (for example, an order on hiring where the code says the employer *may*
  issue one).
- **The sanction beside the duty.** Each finding names the authority (labour inspectorate, court) and the
  sanction from the act in force, or says there is none.
- **Substance over the label.** A civil contract with the marks of employment (subordination, a schedule, the
  employer's tools, one client, a monthly fee) is weighed for requalification; the label in the title does not
  decide it.
- **No invented facts.** Pay, dates, positions and grounds come from the user; unknown → `[DE COMPLETAT: …]` and
  an open question. The person's data never goes into searches or notes.
- **Data of staff** — the notice to employees and monitoring at work belong to `legal-privacy` when it is on;
  this module names the need.
- **Never** sign, register an employee, file with an authority, pay, or send a document to the person: the
  engine prepares; the user acts (`<legal-workflow>/SKILL.md`, approval boundaries).

Resources: [sources](references/sources.md), [examples](examples/requests.md), [behaviour scenarios](tests/scenarios.md) (test inputs, not law).
