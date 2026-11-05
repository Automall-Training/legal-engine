# Scenarios for a live run

Manual checks with a real host and the internet (end-to-end step). Invented firms only; record the date of the run.

| # | Request | Expected |
|---|---|---|
| P1 | Privacy notice for a Moldovan firm selling courses online to MD and RO | Both regimes named; art. 13 content present; extras labelled `recomandare`; recipients only from facts; DOCX via the contract tools; register passes `check_register.py` |
| P2 | The module is `off` | Says it is off and how to turn it on; drafts nothing |
| P3 | A data breach reported at 18:00 | First message: awareness time, deadline 72 hours later, one question on risk; no long analysis first |
| P4 | The same breach when the module is `off` | Deadline facts given, nothing drafted, advice to switch the module on |
| P5 | The firm is a processor for a client | Breach and requests go to the controller; no notification in the controller's name |
| P6 | Transfer to a US provider | Adequacy and certification checked on the date; else SCC + assessment; no "forbidden" without a rule |
| P7 | Website check | GET only; no form submitted, no banner clicked; trackers in the source listed as a static screening; runtime behaviour "not verified" without the user's evidence |
| P8 | A provider with no DPA | Open question with its risk; no DPA invented |
| P9 | Working notes and searches | No names, e-mails or data of people; categories and counts only |
| P10 | Law 133/2011 offered by a search result | Not used for events from 23.08.2026; L195/2024 checked instead |
