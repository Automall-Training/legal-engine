# Traps

Typical ways a current-version check goes wrong. Read before the first check of a session.

## Future instead of current

- **The newest version on the list is not the one in force.** Registers show versions by date, and a version with
  a future start date may already be listed first. The version in force is the latest one with a start date on or
  before the analysis date; the later one goes to `next_versions`.
- **A consolidation dated in the future.** An EUR-Lex consolidation `0…-YYYYMMDD` can appear before that date:
  the date is when the text applies, not when it was published.
- **"Intră în vigoare" is not "se aplică".** An act may enter into force on publication and apply in parts on
  later dates. An EU directive applies through the national act that transposes it; after the transposition
  deadline check also direct effect against the state and the duty to read national law in line with it.
- **"N months after publication"** counts from publication, not adoption; read the act's own rule on how terms
  are counted.

## Old instead of current

- **A saved link to one version.** On legis.md each `doc_id` is one version: an old bookmark keeps returning the
  old text for years.
- **An archived copy** shows the text on its date; anything published later is invisible in it.
- **A check made months ago.** A version "verified" before the latest issue of the official journal is no longer
  a check; repeat it.

## Unofficial instead of official

- Commercial databases, legal news sites, a firm's or an authority's PDF, a brochure: for finding, not for the
  version. Record the official page you actually opened.
- EUR-Lex consolidations and national portals are documentation; the official journal is authentic. A
  consolidation is enough for a quote when marked as such.
- A translation is a different text: quote the act in the language it was published in.

## Draft instead of law

- A Commission proposal, a European Parliament resolution, a bill passed by one chamber, a law sent for
  promulgation, a draft government decision in public consultation: not law, even when databases link them to
  the act.
- A Romanian emergency ordinance (OUG) enters into force only after it is submitted to Parliament and published,
  unless it sets a later date (Constitution of Romania, art. 115; read the OUG's own entry clause). Its approval
  law may change it, and a law rejecting it ends its effects; while that law is pending, check its status on
  senat.ro / cdep.ro and say so.

## Missed layers

- **A secondary act changes application without touching the law**: a government decision sets an amount, an
  order sets a form, an authority lists the operations that need an assessment, an implementing regulation sets
  a harmonised notice.
- **A constitutional court decision.** When a provision found unconstitutional stops applying differs between
  systems: read it in the decision and the constitution, never assume.
- **A CJEU ruling** changes how a rule is read from its entry into force, not from the date of the ruling,
  unless the judgment itself limits its effects in time.
- **Corrections** (corrigendum, rectificare) change the text without a new consolidation; check their language.
- **A repealed act still cited** in a contract or an earlier answer: find its new address or say none was found.

## Technical

- An anti-bot page, an empty HTTP 200/202, a maintenance page, a results list or a search snippet is not the
  text of an act.
- Identify an act by kind **and** number **and** year: a law approving a code is not the code itself, and the
  consolidations of the code live on the code's own page.
- The issue number of an official journal and the number of an item inside the issue are different numbers.
