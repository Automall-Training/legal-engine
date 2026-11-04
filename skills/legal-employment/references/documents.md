# Documents

This file says what each employment document must hold. The library has no employment model card: the structure
below is the module's own, labelled so in the report. Drafting follows `legal-contracts` (`build_docx.py`,
`check_ro_style.py`, `docx_redline.py`, its delivery checklist) in the same matter (`<legal-contracts>/SKILL.md`,
route steps 6–9). A service contract with a self-employed person uses model card M01
(`<legal-contracts>/references/models/01-servicii.ro.md`). The lists are where to look, not the law: each is read
in the code in force on the task date before a document is issued.

| Document | Moldova (where to look) | Romania (where to look) | Required content |
|---|---|---|---|
| Individual employment contract | Labour Code art. 49 (*reported*) | Labour Code art. 17–18 (*reported*), Law 283/2022 | the code's list: parties, place of work, role and duties, start date, duration (and the case for a fixed term), probation, pay and its components, payment dates and method, working time, leave, notice periods, safety risks, the collective agreement if any, social insurance and the other points of the list in force |
| Information before signing | — | art. 17 (*reported*): given before the contract or the addendum | the same elements, in writing; often done by giving the draft contract |
| Telework clauses | the code's telework chapter (*reported*) | Law 81/2018 | where and when the person works, equipment and costs, how work is checked, safety |
| Addendum | the code's amendment rules | art. 41 (*reported*), information before the change | only the changed clauses and the date they apply |
| Hiring order | art. 65 (*reported*): optional | not required by the code | when the user wants one: it repeats the contract and does not add terms |
| Medical certificate (Romania) | — (only listed categories) | art. 27 (*reported*) | obtained before the contract; the employer keeps it |
| Record of hours worked | the code's rule (*reported*) | art. 119 (*reported*) | start and end of each day's work, kept as the code says |
| Safety training record | Law 186/2008, HG 95/2009 | Law 319/2006, HG 1425/2006 | induction at hiring, periodic training, the record signed |
| Job description | where the code or a collective agreement requires it; otherwise optional | annex often used to show the duties; required content per the code | duties that match the role; no promises the employer cannot keep |
| Agreement to end the contract | the agreement ground of art. 81 (*reported*: art. 82¹ or 85(3¹); art. 82 lists endings beyond the parties' will) | art. 55(b) (*reported*) | the date of ending, any payment agreed, the handover |
| Resignation | art. 85 (*reported*) | art. 81 (*reported*) | written by the person; the notice and its waiver |
| Dismissal decision or order | art. 86 and the procedure (*reported*) | art. 61–76 (*reported*), the decision's content | the ground with its article, the reasons, the notice, the term and court to challenge it (Romania), the payments |
| Internal regulation | the code's rules (*reported*) | art. 241–246 (*reported*) | only the topics the code requires plus recorded user decisions |

## How to write them

- **The code's list first.** A contract holds every point of the list in force, in plain words, and nothing that
  breaks the code (a waiver of rights, a penalty on the salary outside the code, a notice shorter than the law).
- **No ballast.** No list of laws, no copied articles, no clauses for situations the employer does not have.
- **One source for the numbers.** Pay, hours and dates appear once; other documents refer to that place.
- **Truthful.** Unknown → `[DE COMPLETAT: …]` and an open question; no guessed salary or date.
- **Person's data** only in the issued documents; the working notes use the role.
- **Existing contracts** are changed with an addendum or real tracked changes and a clean copy.
