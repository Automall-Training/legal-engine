# Documents

This file says what each privacy document must hold. The drafting itself follows `legal-contracts`: its model card,
`build_docx.py`, `check_ro_style.py`, `docx_redline.py` and its delivery checklist, in the same matter
(`<legal-contracts>/SKILL.md`, route steps 6–9). Model cards are structure, not law; the law is checked per
[law-map.md](law-map.md) on the task date.

| Document | Model card | Required content (check the article on the task date) |
|---|---|---|
| Privacy notice (website, form, app) | M08 `08-informare.ro.md` | art. 13 (data from the person) or 14 (from elsewhere): controller and contact, DPO contact if there is one, purposes and lawful basis of each, legitimate interest when relied on, recipients or their categories, transfer abroad and the safeguard with how to get a copy, retention period or its criteria, rights, withdrawal of consent, complaint to the authority, whether data is required by law or contract and what happens without it, automated decisions |
| Cookie notice and banner text | none in the library: own structure, labelled so | which cookies, purpose, duration, who sets them; consent before non-essential ones; refuse as easy as accept; how to change the choice |
| Consent wording (newsletter, marketing, special data) | part of M08 | one purpose per consent, plain words, not pre-ticked, separate from terms, how to withdraw |
| DPA (the firm as controller or processor) | M06 `06-dpa.ro.md` | art. 28(3) content; sub-processors and how changes are announced; breach help; deletion or return |
| Transfer clauses | M07 `07-transfer.ro.md` | the official SCC text as published, only the module and options that fit, annexes completed; a transfer assessment beside it |
| Record of processing | M09 `09-registru.ro.md` | art. 30(1): controller, purposes, categories of people and data, recipients, transfers and safeguards, retention, security measures; art. 30(2) for a processor |
| Joint controllers arrangement | M10 `10-operatori-asociati.ro.md` | art. 26: who does what (notice, requests, breaches), the essence made available to people |
| Reply to a data request, breach notification, message to people | none: short letter | the procedure's content in [procedures.md](procedures.md); dates computed and written |

## How to write them

- **Minimum the law asks of this text.** Countries, recipient names and detailed retention schedules live in the
  record of processing; the notice gives categories and criteria and offers details on request, unless the law
  or the user's choice says otherwise. Each extra line is labelled `recomandare` in the report.
- **No ballast.** No list of laws, no authority's address where the text does not need it, no obligations beyond
  the law (own deadlines, extra registers, pre-notifications), no empty promises ("we never share data").
- **Truthful.** Every recipient, country and retention period comes from the facts of the matter; unknown →
  `[DE COMPLETAT: …]` and an open question, never a plausible guess.
- **The user's existing document** is edited with real tracked changes plus a clean copy; it is rebuilt only when
  the user asks.
- **Where it lives.** The user keeps the documents in force (notice, record, DPAs) where they choose; the setup
  step `documents` copies them into `<profile>/contracts/`, and the next matter starts from that copy.
- The engine never publishes the notice or changes the website: it delivers the text and, when useful, a short
  brief for the web developer.
