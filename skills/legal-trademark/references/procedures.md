# Procedures

Each procedure is a checklist with an outcome. The outcome is one or more of: **D** — a document in `output/`;
**M** — a measure the user takes (who, what, by when); **Q** — one question to the user, options with the
recommended one first; **T** — deadlines from `tm_deadlines.py`, each with its rule and "check on the task date".
Working notes go to `<matter>/work/`: offices, numbers, classes and dates, no names of private individuals.
Article references follow [law-map.md](law-map.md) and are read on the task date before they carry a conclusion.

Every procedure looks for the way that lets the user keep working under the sign at the lowest cost and an
acceptable risk (`norms.md` §2, §15), and states plainly a real conflict with an earlier right.

## 1. Name check (clearance)

- [ ] The sign or the candidates, what they will be used for, the territories now and planned, the classes.
- [ ] Inherent problems first: descriptive or generic words, misleading terms, protected emblems; a combined
      sign with a distinctive element may pass where the word alone does not.
- [ ] Earlier rights in [sources.md](sources.md): identical and similar signs in the same and related classes,
      firm names, domains, visible unregistered use. Record each check.
- [ ] For each conflict: the earlier right's territory, classes, status, age (older than five years and unused?
      → it can be challenged), the owner's activity.
- [ ] Verdict per sign and territory on the scale of `norms.md` §5 (`se poate` · `se poate cu condiție` · `risc`
      · `interzis`), the sources and the date. Never "available" or "free" (law map, known traps).
- [ ] Ways around a conflict before dropping the name: other classes or a narrower specification, a distinctive
      element, another territory first, a coexistence or consent agreement, a non-use challenge, a variant.

**Outcome:** D (a clearance note: sign · territory · verdict · conflicts · ways around · sources and date) · Q
(choose among the signs or the ways around).

## 2. Filing strategy

- [ ] Follow [filing-strategy.md](filing-strategy.md): two to four configurations with cost from the current
      fee lists (dated), residual risk and verdict; the first one the cheapest that covers today's market.
- [ ] The list of goods and services in the classification terms, limited to real use and plans.
- [ ] Who files: the user themselves where the law allows it, or a representative where it requires one.
- [ ] A logo: the economic rights of its designer or agency transferred in writing before filing.

**Outcome:** D (the strategy table and the draft list of goods and services) · Q (the configuration) · M (the
user or their representative files and pays; the engine never does).

## 3. Portfolio and deadlines

- [ ] The portfolio lives in `<profile>/trademarks/portfolio.json` (shape: `templates/portfolio.json`). A new
      mark or a status from an office letter is written there only after the user confirms it; a number or a
      date that is not on a document of the office is left `null`.
- [ ] `python3 <skill-dir>/scripts/tm_deadlines.py portfolio --file <profile>/trademarks/portfolio.json`:
      deadlines nearest first; urgent ones (under 14 days) open the answer.
- [ ] Each date: the rule, the article, `reported` or `not-read`, "raw date, check on the task date". A
      deadline that carries money or the right (certificate fee, renewal grace) is read in the official text in
      the same matter before it is relied on.
- [ ] Gaps: a territory or class the business uses but the portfolio does not cover; a mark nearing five years
      without use evidence (keep dated invoices and pages per territory); an owner who is not the firm using the
      mark (no licence); a logo whose rights were never transferred by its designer.
- [ ] An invoice or "register entry" offer after publication: pay only through the office's own channel.

**Outcome:** T · Q (fill a gap or not, recommended option first) · M (pay, renew, collect use evidence).

## 4. Office letter (deficiency, objection, provisional refusal)

- [ ] The office, the document, the date it was received and the term it sets; the term in the law if the
      letter gives none. Urgent first.
- [ ] What exactly is objected to: form, classification, absolute grounds (descriptive, misleading), or an
      earlier right.
- [ ] Options: correct the form · limit the goods and services · argue (distinctiveness acquired by use,
      practice of the office) · drop the classes in trouble and keep the rest · let it go and refile better.
- [ ] Each option with cost and chance; the cheapest one that keeps the useful protection first.

**Outcome:** D (a draft reply or the arguments for the representative) · T · Q (which option).

## 5. Opposition

- [ ] **Against another's filing**: our earlier right must be older (filing or priority date) and in force in
      the territory of the filing; same or similar sign and goods; the window from the law map (OSIM counts from
      the admission). No earlier right there → no opposition; third-party observations only for absolute grounds.
- [ ] Before opposing: is a letter or a coexistence agreement cheaper? Is the other side active in our market?
- [ ] **Against our filing**: is their right older, registered for those goods, in force and, if older than five
      years, used (a request for proof of use)? Options: limit our goods, negotiate coexistence, defend, withdraw
      a class.
- [ ] The cooling-off period and the next terms of the procedure.

**Outcome:** D (an opposition or defence brief for the user or the representative) · T · Q (oppose, negotiate,
limit or let go).

## 6. Someone uses our sign

- [ ] Our right in that territory and for those goods: registered · applied (rights "subject to registration")
      · none (only unfair competition, copyright in a logo or a firm name — weaker, said so).
- [ ] Evidence: dated screenshots or saved pages, the seller, the goods, the territory; captured again before
      each next rung.
- [ ] The ladder, one rung at a time, each step prepared and the user acts:

| Rung | What | Note |
|---|---|---|
| 0 | record and recheck later | when the use is small, old or ambiguous |
| 1 | a report to the platform (marketplace, social network, app store, host) | through its own form; under the DSA notice and action in the EU |
| 2 | a polite letter from the owner: stop, no money demands | for an application: a notice "subject to registration", no deadline to stop |
| 3 | one reminder | before it, fresh evidence |
| 4 | a representative or lawyer: court, customs, domain dispute | costs named before; the user decides |

- [ ] No threats of police or criminal complaints in rungs 1–3; no `®` for an application; no list of laws in the
      letter.

**Outcome:** D (the report text, the letter, a file for the lawyer) · Q (the rung) · M (the user sends).

## 7. A claim against us

A warning letter, a platform takedown, an opposition, a pre-trial request (Moldova: a term may run from receipt,
*reported* art. 62 of Law 38/2008).

- [ ] Received when, by whom (a firm or a person), what they claim, what term they give, and the legal term if
      any. Urgent first.
- [ ] Their right: registered where, for what, since when, used? Our own right or earlier use? A firm name or
      domain of ours?
- [ ] Options in order of cost: explain a difference (goods, territory, sign) · a small change (logo, a
      distinctive element, the goods listed) · coexistence · a phased rebrand · challenge their right (non-use,
      invalidity, bad faith) · defend in court.
- [ ] Nothing is admitted or promised in the first reply without the user's decision.

**Outcome:** D (a reply draft or a brief for a lawyer) · T · Q (the option).

## 8. Licence and ownership

- [ ] Who owns each mark and who uses it. A person who owns and firms that use → a licence to each firm, or an
      assignment to the firm; a sale of the business → an assignment and its recording at the office.
- [ ] The licence: the mark and its number, territory, goods, exclusive or not, term, quality control, fees or
      none, recording at the office when it should bind third parties (*reported*).
- [ ] Drafting by `<legal-contracts>` model card M05 (structure; the trademark points come from this list),
      route steps 6–9.

**Outcome:** D (licence or assignment) · M (signing and recording are the user's).
