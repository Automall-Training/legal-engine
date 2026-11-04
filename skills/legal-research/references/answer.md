# The answer

How a reasoned answer to "can I…", "is it legal…", "which rule applies", "what is the deadline / sanction"
is laid out. The substance rules are `<legal-workflow>/references/norms.md` (§2 path first, §3 three layers,
§4 title or activity, §5 weight of a risk, §6 decide or ask, §13 no invented facts, §14 two kinds of check);
this file only arranges them. Shell: [`../templates/answer.md`](../templates/answer.md).

## Before writing

1. **The question as asked**, then the question as it must be answered: who acts, what, where (which
   jurisdiction's rules apply — `<legal-workflow>/references/jurisdiction.md`), on what date. A question about a
   past event has its own analysis date; a question about future conduct is answered as of today, with changes
   already adopted listed separately.
2. **Facts.** Confirmed facts, assumptions and unknowns kept apart. An unknown that decides the answer gives
   conditional answers ("if your buyers are consumers… / if they are firms…") and names the fact that picks one;
   ask it only if it is material and cannot be answered by both branches.
3. **Rules.** Find candidate rules by subject, never with the user's names, figures or confidential text. For
   each act the answer rests on run the current-version check ([version-check.md](version-check.md)); record each
   cited provision in the source register.

## Blocks of the answer (in this order)

1. **Short answer** — two or three lines: the verdict (`se poate` / `se poate cu condiție` / `risc` /
   `interzis`) and the main condition. If something material is not verified, say so here, not only at the end.
2. **What the law directly requires or forbids** — only `cerință legală`: the provision (act, article, version),
   a short quote in the original language, the sanction and the authority; "no sanction" when there is none. For
   a regulated profession: is the title protected, or a list of reserved acts?
3. **Readings and practice** — `interpretare prudentă`: whose reading (authority guidance, court practice,
   doctrine), how the market does it. Never presented as block 2.
4. **How to do it lawfully** — the concrete path: conditions, wording, structure, documents, steps, simplest
   first. "No" only for a direct prohibition with the rule named, and then the nearest lawful alternative.
5. **Risk** — per point: sanction, authority, likelihood (low / medium / high, no invented percentages), market
   practice, verdict. Low risk: the engine picks the business option and writes "decided by the engine". Medium
   or high, money or the business model: one question to the user with options, recommended first.
6. **Sources** — per act: title and number, version (label and date), cited provisions, URL, time opened, card
   result (`current` / `outdated` / `not_verified`), and whether quotes were machine-checked.
7. **Not verified** — every open point, what it blocks and how to close it. Never omitted when not empty; never
   turned into "no changes".

Labels: every conclusion, every option offered and every "I recommend" carries one of `cerință legală`,
`interpretare prudentă`, `recomandare`. Quotes stay in the language of the act; everything else is in the
conversation language.

## Where it goes

A reasoned answer is `<matter>/output/answer.md` (conversation language) plus `source-register.json` and the
cards in `work/versions/`. A quick factual reply in the conversation (no matter) still names its sources and
what was not verified. High stakes (court, large sums, criminal or administrative liability): say that this is an
assistant, not a lawyer, and suggest a licensed lawyer for the final decision.

## Self-check before delivery

`norms.md` §15, plus: is every quote from the version in force on the analysis date? Is any future version,
draft or guidance presented as law? Does any conclusion rest on an act whose card is `outdated`?
