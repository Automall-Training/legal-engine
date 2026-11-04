---
name: legal-privacy
description: Personal data module of the legal engine (Moldova, Romania, EU) - GDPR, Moldovan Law 195/2024 and Romanian Law 190/2018. Privacy notice, cookie banner and consent, processing agreement (DPA), joint controllers, transfers abroad (SCC, transfer assessment), record of processing, DPIA screening, data subject requests and data breaches (72 hours), checked against the official text on the task date. Works inside a matter opened by legal-workflow, only when the module is on. Use for "политика конфиденциальности", "cookies", "согласие на обработку данных", "DPA", "утечка данных", "запрос на удаление данных", "GDPR", "politica de confidențialitate", "date cu caracter personal", "încălcarea securității datelor", "privacy policy", "data breach", "data processing agreement".
---

# Legal Privacy

Resolve this skill's directory (`<skill-dir>` below); the entry skill is `<skill-dir>/../legal-workflow/`
(`<legal-workflow>` below) and the contract tools are in `<skill-dir>/../legal-contracts/` (`<legal-contracts>`).
The law method, the working norms and the approval boundaries live in `<legal-workflow>` and are followed by
reference, never copied. This module decides **what** a privacy document or measure must contain; the DOCX, the
Romanian style check and the tracked changes are made with the contract tools.

## Before anything

1. **Breach first.** If the request is a data breach (leak, hack, lost device, e-mail to the wrong person), go to
   procedure 6 of [procedures.md](references/procedures.md) at once: the 72-hour clock may be running, and the
   first message gives the deadline and the one question that decides it.
2. **Module on?** `python3 <legal-workflow>/scripts/legal_profile.py module privacy` → `on` continues. `off` →
   say the module is off and that the setup wizard (step `modules`) or `legal-workflow-update` turns it on; do
   nothing else in this area. `unset` → run the wizard's step `modules`. A breach is answered even when the
   module is off or setup is unfinished (the router sends it here first): the deadline facts and the advice to
   switch it on, nothing drafted; those facts are labelled "not verified on the task date" unless art. 33 of
   GDPR or L195/2024 was read in the official text today.
3. **Handoff.** Work needs what `<legal-workflow>/references/matters.md` § "Handoff to a module" lists. Called
   directly without it → load `<legal-workflow>/SKILL.md`, follow its Start, then come back.
4. **Norms.** Read `<legal-workflow>/references/norms.md` once per session and [law-map.md](references/law-map.md)
   before the first conclusion.

## Route

1. **Facts** — which firm acts (the profile's `context/company.md`), what data, whose (clients, website visitors,
   employees, children), for what, where it goes (hosting, e-mail, CRM, payment, analytics, video calls), which
   countries. Facts come from the user, the profile and the user's documents; never invent a processor, a country
   or a contract. Record them: `python3 <legal-workflow>/scripts/legal_profile.py matter update <id> --data
   @<matter>/work/intake-update.json` (shape: [templates/module-data.json](templates/module-data.json)).
2. **Regime** — GDPR, L195/2024 (MD) or both, by establishment and by whom the firm offers to
   (`<legal-workflow>/references/jurisdiction.md`; GDPR art. 3, L195 art. 3). Each regime answered on its own.
3. **Role** — controller, processor, joint controllers or an independent controller (a bank, a payment provider),
   by who decides purposes and means, not by the contract title or the tax regime.
4. **Procedure** — one of [procedures.md](references/procedures.md): new website or channel · processor or DPA ·
   transfer abroad · DPIA screening · data subject request · data breach. Each ends in a document, a measure for
   the user, or one question.
5. **Law check** — every material conclusion rests on the official text read on the task date:
   `<legal-workflow>/references/law-check.md`, the source register and `check_register.py`, and the current-version
   card of `<skill-dir>/../legal-research/references/version-check.md` for each act relied on.
6. **Documents** — [documents.md](references/documents.md): the minimum content of each document, the model card
   of `<legal-contracts>/references/models/` (M06–M10), then `<legal-contracts>` route steps 6–9 (model, reconcile,
   deliver) in the same matter. The user's own text is edited with real tracked changes, never rebuilt.
7. **Deliver** — deliverables in `output/`, a short report (scope, regime, role, what is required by law and what
   is only recommended, risk with its weight, sources, not verified, what the user does next); log `waiting` or
   `done` through `legal_profile.py matter log`.

## Rules of this module

- **Law-required first, extra labelled.** A notice holds what the law asks of that text; anything more is marked
  `recomandare` and added only when it removes a real risk. No list of laws, no own deadlines shorter than the
  law's, no promise the firm cannot keep.
- **No personal data in working files or searches.** Logs of requests and breaches carry categories, counts,
  dates and channels, never names, e-mails or the data itself. A search query names the topic, never the person.
- **A missing DPA, an unknown country or an unknown role** is written as an open question with its risk, not
  filled in by guess.
- **Never** publish a notice, change a website, a banner or an account, notify an authority or write to a data
  subject: the engine prepares the text and the steps; the user acts (`<legal-workflow>/SKILL.md`, approval
  boundaries).

Resources: [examples](examples/requests.md), [behaviour scenarios](tests/scenarios.md) (test inputs, not law).
