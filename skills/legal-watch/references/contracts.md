# Contracts in force: the clause index and re-review

The user's contracts in force are copies in `<profile>/contracts/` (step 8 of the wizard, or later on request);
the originals are never touched. Each gets an index `contracts/index/<file-stem>.json`:

```json
{"schema_version": 1, "contract": "services-2025.docx", "jurisdiction": "RO", "indexed_on": "2026-11-04",
 "clauses": [
   {"clause": "7.1", "topic": "personal data", "acts": [{"id": "eu.reg.2016-679", "provision": "art. 28"}],
    "source": "cited", "needs_reverify": false, "reverify": []},
   {"clause": "4.3", "topic": "late payment interest", "acts": [{"id": "ro.oug.13-2011", "provision": null}],
    "source": "inferred", "needs_reverify": false, "reverify": []}]}
```

## Building an index

1. `watch index scan <profile>/contracts/<file> --jurisdiction MD|RO` prints a draft from the citations in the
   text (laws, government decisions, ordinances, codes, EU regulations and directives, with the article when one
   is cited). `--write` saves it; an existing index is never replaced without `--force`.
2. Read the contract and complete the draft by hand: give each row a `topic`; add `inferred` rows for clauses
   whose subject is governed by an act they do not cite (payment terms, liability limits, withdrawal, personal
   data, employment terms, jurisdiction); drop citations that do not bear on a clause (a law named only in the
   definitions). Keep it short: only clauses a change of law could break.
3. Every act of an index must be in the watchlist, or its changes will never reach the clause:
   `watch index check` lists the missing ones; add them in the watchlist (setup.md §7).

The index names clause numbers and laws, never the parties or amounts: the working notes stay anonymous.

## When a law changes

A confirmed change (`new_in_force`, `new_future`, `repealed`) marks every clause that depends on that act:
`needs_reverify: true` with the change in `reverify`. A change that is only *possible* flags nothing.
`watch index pending` lists what waits. For each contract, propose one matter:

```bash
python3 <legal-workflow>/scripts/legal_profile.py matter new --slug reverify-<file-stem> --title "Re-review <file>" --module contracts
```

The matter audits the flagged clauses against the new version (read on the task date through `legal-research`),
proposes a Word redline or an addendum through `legal-contracts`, and the user decides. A future change is
prepared before its start date; nothing is sent to the other party by the engine. When the matter is delivered:
`watch index clear --contract <file> [--clause N] --matter <matter-id>`; the flag moves to `reviewed` with the
matter id.
