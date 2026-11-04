---
name: legal-consumer
description: Online sales to consumers module of the legal engine (Moldova, Romania, EU) - terms of a shop or a course site, information before the order, the order button, the 14-day withdrawal and its exceptions for digital content, the online withdrawal function, conformity guarantee for goods and digital content, price and discount display, unfair terms, consumer complaints, checked against the official text on the task date. Works inside a matter opened by legal-workflow, only when the module is on. Use for "условия продажи", "публичная оферта", "возврат денег за курс", "право на отказ", "жалоба покупателя", "termeni și condiții", "dreptul de retragere", "ANPC", "reclamație client", "terms of sale", "refund policy", "withdrawal right".
---

# Legal Consumer

Resolve this skill's directory (`<skill-dir>` below); the entry skill is `<skill-dir>/../legal-workflow/`
(`<legal-workflow>` below) and the contract tools are in `<skill-dir>/../legal-contracts/` (`<legal-contracts>`).
The law method, the working norms and the approval boundaries live in `<legal-workflow>` and are followed by
reference, never copied. This module decides **what** a sale to a consumer must show and allow; the DOCX, the
Romanian style check and the tracked changes are made with the contract tools.

## Before anything

1. **Module on?** `python3 <legal-workflow>/scripts/legal_profile.py module consumer` → `on` continues. `off` →
   say the module is off and that the setup wizard (step `modules`) or `legal-workflow-update` turns it on; do
   nothing else in this area. `unset` → run the wizard's step `modules`.
2. **Handoff.** Work needs what `<legal-workflow>/references/matters.md` § "Handoff to a module" lists. Called
   directly without it → load `<legal-workflow>/SKILL.md`, follow its Start, then come back.
3. **Scope.** Consumer = a natural person buying outside their trade. A sale only to firms is `legal-contracts`.
   The personal data part of a shop (notice, cookies) is `legal-privacy` when it is on; this module names the
   need and does not draft it.
4. **Norms.** Read `<legal-workflow>/references/norms.md` once per session and [law-map.md](references/law-map.md)
   before the first conclusion.

## Route

1. **Facts** — seller (the profile's `context/company.md`), what is sold (goods, services, digital content or a
   digital service, a course live or recorded, a subscription), channel (website, app, marketplace, social
   network, phone), where the buyers live, how they order and pay, when access or delivery starts. Record them:
   `python3 <legal-workflow>/scripts/legal_profile.py matter update <id> --data @<matter>/work/intake-update.json`
   (shape: [templates/module-data.json](templates/module-data.json)).
2. **Regime** — when the seller directs its activity to the buyer's country, a choice of law in the terms cannot
   take away that country's mandatory consumer protection (Rome I art. 6 before EU courts;
   `<legal-workflow>/references/jurisdiction.md`). A Moldovan seller with Romanian buyers checks the Romanian and
   EU rules for them; each regime answered on its own.
3. **Checkpoints** — [checkpoints.md](references/checkpoints.md): go through every point that fits the sale and
   mark it met · missing · not applicable · not verified, each with the rule, the sanction if one exists, and the
   simplest lawful fix.
4. **Law check** — every material conclusion rests on the official text read on the task date:
   `<legal-workflow>/references/law-check.md`, the source register and `check_register.py`, and the current-version
   card of `<skill-dir>/../legal-research/references/version-check.md` for each act relied on.
5. **Documents** — terms of sale and withdrawal information: model card M03
   (`<legal-contracts>/references/models/03-termeni.ro.md`, written for courses; for goods it is a structure only),
   then `<legal-contracts>` route steps 6–9 in the same matter. The official withdrawal form is taken from the act
   in force on the task date, never rewritten from memory. The user's own terms are edited with real tracked
   changes, never rebuilt.
6. **Deliver** — deliverables in `output/`; a short report: the checkpoint table, what is required by law and what
   is only recommended, risk with its weight, sources, not verified, what the user changes on the site (a brief for
   the web developer when useful); log `waiting` or `done` through `legal_profile.py matter log`.

## Rules of this module

- **Required only what the law requires.** Anything beyond the information lists, the button, the withdrawal and
  the guarantees is `recomandare` and added only when it removes a real risk. No own deadlines or promises that
  are stricter than the law unless the user wants them.
- **The sanction beside the duty.** Each finding names the authority and the sanction range from the act in force
  (or says there is none) and how likely a check or a complaint is.
- **Market practice is a risk argument, not a rule.** How other sellers write it may show what the authority
  tolerates; it never replaces the text.
- **The simplest lawful option first**: one tick box with the confirmation e-mail instead of a chain of
  declarations.
- **Never** publish terms, change the site or reply to a customer or an authority: the engine prepares; the user
  acts (`<legal-workflow>/SKILL.md`, approval boundaries).

Resources: [examples](examples/requests.md), [behaviour scenarios](tests/scenarios.md) (test inputs, not law).
