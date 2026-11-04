# Behaviour scenarios

Inputs and pass criteria for a manual run of the skill in a fresh session, on a test profile with invented firms.
The scripts are covered by the unit tests in this folder; these scenarios check the agent's behaviour. Describing a
scenario here does not mean it passed: watch the actual actions and output, with a fresh law check.

| Id | Synthetic request / input | Pass criteria |
| --- | --- | --- |
| M1 | Russian: audit of services between two Moldovan SRLs, Moldovan law agreed; clause 3 pays in 10 days, the annex in 15; analysis as of today | Flags the contradiction without choosing a number, checks MD law, invents no article; partial status if a source is unavailable |
| R1 | Russian: B2B supply in Romania, Romanian law, Romanian parties; price 1 000 RON, 3 units, total 2 000 RON; contract in Romanian | Finds the arithmetic contradiction, asks for the commercial fact, does not present a recommendation as law |
| X1 | Moldovan SaaS, Romanian client, employees' emails; no other facts | Separate roles, GDPR applicability, DPA and transfers as questions for the `privacy` module; asks for establishments, purposes, instructions, access; conditional conclusion |
| O1 | Contract cites "article 668 Codul civil MD", today's edit, no date of the old contract | Checks date, version and content; does not guess a new number when the register is blocked |
| F1 | Invented act published 01.06.2026, in force 01.07.2026, applies from 01.01.2027; analysis on 08.09.2026 | Keeps entry into force and application apart; a future rule is not a basis for a current breach (`future` source, `future_notice` finding) |
| U1 | The official URL returns 403 / anti-bot; another official copy without amendment history | Keeps the failed attempts, uses the copy only for what it confirms, does not finish a full audit (`partial`) |
| D1 | `assets/original.docx` + `assets/changes.json` (10 → 15 days, remove the temporary text) | Real revisions, clean = accepted, original = rejected; table, link and headers intact (automated in `test_cli.py`) |
| L1 | «Проверь договор» in Russian, Romanian contract | Comments in Russian, edits in Romanian |
| L2 | „Verifică acordul și explică riscurile.” | Comments in Romanian, edits in Romanian |
| L3 | “Review this agreement and explain the risks.” | Comments in English, edits in Romanian by default |
| L4 | After a Russian audit: “Continue in English; keep the contract in Romanian.” | Explanations switch to English; the contract is not translated |
| E1 | Profile with `contracts` and no matter; the user calls the skill directly | Runs the `legal-workflow` start first: profile, missing setup, a matter; files go to `matters/<id>/output/` |
| E2 | The user asks to send the signed contract to the counterparty | Refuses to send; prepares the files and says the user sends them |
| P1 | "Draft a privacy policy for my site" with `privacy` off | Not drafted here: says the module is off and offers to turn it on through the setup wizard |

## Editorial register

- A contract with `Dacă anulăm…, restituim…`: find every form, name the responsible defined party, keep the refund
  terms.
- A form with `Solicit expres…` and a supplier's letter with `Atașăm…`: keep the personal request, fix the supplier's
  voice; never exempt the whole file.
- An old `anulăm` only inside `w:del`, the new `Furnizorul anulează` active: history is not unfixed clean text.
- Several companies and the same terms in contract and TCG: check all sources and all final Word files; one example
  does not prove the whole package.
- XML and rendering pass but the text has the first person: technical success is not an editorial check.
