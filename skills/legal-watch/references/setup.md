# Setup steps of the law library: `niches`, `laws`, `first-run`

The wizard (`legal-workflow-setup`) calls this file for its questions 6, 7 and 10. One question at a time,
options with the recommended one first and a short note on what each changes. After each step:
`python3 <legal-workflow>/scripts/legal_profile.py step set <id> --status done` (or `skipped`). Re-running a step
shows the current choice first and changes only what the user changes.

## 6. `niches` — business niches and law categories

1. Read the user's firms and audience from `context/company.md` (countries, activity, B2B or B2C).
2. Show the niches: `watch catalog niches`. Suggest the ones that match the activity; the user may pick several
   or describe their own (then pick the closest niches and add acts by hand in step 7).
3. Show what the choice means: `watch suggest --niches a,b [--b2c] --countries MD,RO,EU`. General categories come
   for every business (civil, tax, accounting, company, personal data), consumer law when the user sells to
   people, the niche categories after them. The user ticks the categories to keep; recommended: all suggested.
4. Write nothing yet if step 7 follows in the same session; otherwise write the watchlist with the defaults of
   step 7 (`watch init … --acts all`).

Skipped → no watchlist; the step `laws` is skipped too and monitoring stays off until the user asks for it.

## 7. `laws` — what to download, how often, how to read

Three questions, in this order:

1. **Which acts.** Options: all acts of the chosen categories (recommended) · only the main ones (`p1`) · choose
   from the list (`watch catalog acts --countries …`). An act the catalog lacks is added by id with title,
   jurisdiction and its official source (watchlist format below).
2. **How often.** Weekly on this computer (recommended: Monday morning, local job) · only when I ask · a weekly
   Claude scheduled task. See [engines.md](engines.md) for what each needs.
3. **How to read the sites.** Free automatic reading with a check by hand of what the sites block (recommended:
   `urllib,host`) · plus a local browser (`urllib,playwright,host`; installs Playwright) · plus the user's own
   command for a paid reading service (`command`; the user writes the command, the engine never sees a key) ·
   only by hand (`host`). Say plainly that several official portals block automatic reading, so some acts
   will need a check by hand in any case.

Then: `watch init --niches … --categories … --acts all|p1|<ids> [--b2c] --countries … --language <digest language
from context/language.md> --engines … [--fetch-command …] --schedule …` (add `--force` when replacing a watchlist:
the state and the stored texts are kept).

## 10. `first-run` — first download and a trial run

1. `watch run` (the first run records every act's baseline and stores its official text).
2. Read the digest with the user: how many acts were read, which stayed "not verified" and why. Offer to check the
   p1 ones by hand now (monitoring.md, "Host check"); the user may postpone.
3. If contracts in force were copied into `contracts/` (step 8), build their indexes now ([contracts.md](contracts.md)).
4. Schedule: if the user chose weekly local runs, show `watch schedule plan` and, after their yes,
   `watch schedule install` (macOS) or give the cron line ([engines.md](engines.md)).
5. Mark `first-run` done even when some acts stay not verified (the digest says so); `skipped` if the user
   postponed the run.

## Watchlist format (`<profile>/laws/watchlist.yaml`)

```yaml
schema_version: 1
settings:
  countries: [MD, RO, EU]        # filters catalog suggestions
  language: ru                   # language of the digest: ru | ro | en
  engines: [urllib, host]        # in order: urllib | playwright | command | host
  fetch_command: null            # with `command`: the user's own command containing {url}; prints the page
  schedule: weekly               # on-request | weekly | claude-schedule
niches: [online-courses]
categories: [civil, tax, accounting, company, data, consumer, digital-content]
acts:
  - id: ro.lege.287-2009         # from the catalog: the id is enough
  - id: md.lege.1-2026           # own act, not in the catalog (invented example)
    title: Legea nr. 1/2026 cu privire la exemplu
    jurisdiction: MD
    priority: p2                 # p1: an unverified act makes the run incomplete
    sources:
      - {kind: legis_md, doc_id: "000000"}   # legis_md | just_ro (doc_id) | eurlex (celex)
```

The watchlist holds choices and may be edited by hand; the facts read from official pages live in
`laws/state.json` and are written only by the scripts. A wrong edit is reported by every command with the field
to fix.
