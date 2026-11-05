# The law library: what is stored, where, and how the skills use it

The engine keeps a memory of **what it saw on the official sites and when**. It never keeps the law of today:
every conclusion "the rule is in force" is re-checked against the official text on the task date
(`<legal-workflow>/references/law-check.md`). The library answers "which version did we see, on which day, and
what exactly did we read", and gives the next check a point to compare with.

## Layers

| Layer | Where | What it is | Written by | Truth? |
|---|---|---|---|---|
| Catalog | engine, `assets/catalog/acts.json`, `niches.json` | 116 acts (MD, RO, EU), where to find each, niche → categories → acts; each act `verified` or `reported` with its check date | the engine's authors | no: navigation |
| Watchlist | profile, `laws/watchlist.yaml` | the acts this user follows, their sources, engines, language, schedule | the wizard, `watch init`, `watch source add`, the user by hand | the user's choice |
| State | `laws/state.json` | per act: version in force and next version held, repeal, hash, url, engine, `checked_on`, last copy; Gazette scan point and pending signals; last 30 runs | runs and `watch record` only | no: "seen on day X" |
| Text copies | `laws/texts/<act>/<date>-<hash12>.txt` | the official text exactly as read, one file per distinct text | a checked reading only | no: evidence |
| Runs | `laws/runs/<date>/run.json`, `digest.md` | each day's full result and short digest | runs | no: a journal |
| Error log | `laws/issues.json`, `laws/report.html` | what could not be read and what to do ([issues.md](issues.md)) | runs | no: a to-do list |

The catalog is shared and public; everything else is the user's and lives in their profile, never in the engine.
The watchlist (choices) and the state (facts) are kept apart: editing the watchlist never breaks the held
versions, and a lost state only means the next run records new baselines.

## How a version gets in

1. A run reads the act's official page with a calibrated reader, or the agent checks it by hand and records a
   version card (`watch record`).
2. The first reading is a **baseline**. Later readings are compared by start date: a later date in force is a new
   version, a date still ahead is the next version, never "in force".
3. Only a checked reading moves the state and saves a text copy. A failure, an archived copy or an uncalibrated
   reader changes nothing in the library and goes to the error log.

The state keeps the current and the next version; older versions remain as their text copies (the history of
versions is the folder `texts/<act>/`).

## How the other skills use it

- **Before a task:** `watch show` gives, per act, the version held, when it was checked, its hash and its text
  copies. It tells the agent what to expect and which acts the user follows; it is not a source.
- **During the task:** the official text is opened again on the task date and a version card is made
  (`<legal-research>/references/version-check.md`), with `held_version` taken from `watch show`. A card differing
  from the held version is a finding: tell the user and run `watch run --acts <id>`.
- **After the task:** a card from today about the whole act (`scope: "text"`, `cited_provisions: ["whole act"]`)
  also updates the library with `watch record --card … --root <matter>`: one reading serves the task and the
  monitoring. A card about some articles or another date is task evidence only.
- The matter keeps its own copy of what it read (`<matter>/work/sources/`): the card's checker reads it there, and
  a matter must stand on its own when archived. The library copy is the monitoring's evidence. Two copies of a
  small text are the price of keeping the two apart.

## Keeping and cleaning

- Nothing is deleted automatically. Text copies are kept forever: they are small and they are the version history.
- `watch prune --runs-older 365` lists old run folders; with `--apply` it deletes them. Only on the user's request;
  at least 30 days are always kept (the health line reads recent runs). The state, the error log and the text
  copies are never pruned.
- To start a library over, the user moves `laws/state.json` away; the next run records baselines again.

## Known gaps

- 38 catalog acts (15 of them p1) have no official source yet: they stay "not verified" until the agent finds
  their page and runs `watch source add` (recipe `no_source` in [issues.md](issues.md)).
- Moldovan document ids are `reported`: a legis.md id names one version; the run follows its page to the later ones.
