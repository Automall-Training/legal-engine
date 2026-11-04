# Fetch engines and the schedule

## Engines (`settings.engines`, tried in order)

| Engine | Cost | What it needs | Honest limits |
|---|---|---|---|
| `urllib` | free | nothing (Python standard library) | several official portals block it or drop the connection: those acts end "not verified" |
| `playwright` | free | `WITH_PLAYWRIGHT=1 ./install.sh` (a local browser) | anti-bot pages are never bypassed; slower; the browser profile lives in `laws/.browser/` |
| `command` | the user's choice (for example a paid reading service) | `settings.fetch_command`: the user's own command with `{url}`, printing the page (HTML or markdown) to stdout | the user sets up the service and its key themselves; the engine passes only the URL and never reads, asks for or stores a key |
| `host` | free | the agent in a conversation | not automatic: acts left not verified are checked by hand (monitoring.md, "Host check") |

When an engine fails on a page, the next one is tried; the run records which engine produced each reading
(`evidence.via`). The EU fallback to the Publications Office (Cellar) uses plain HTTP, so it runs only when
`urllib` is among the engines; with `host` alone, scripts open no page at all. Every engine sends GET requests
to public pages only, waits 5–15 s between pages, and never fills forms, logs in or solves a CAPTCHA.

## Schedule (`settings.schedule`)

| Choice | How | Who installs it |
|---|---|---|
| `weekly` (default) | macOS: a launchd job every Monday 09:00 (`watch schedule plan`, then `watch schedule install`); Linux: a cron line (`watch schedule plan --kind cron`) | launchd: the script, only after the user's explicit yes in chat; cron: the user, with `crontab -e` |
| `claude-schedule` | a weekly Claude scheduled task with the prompt from `watch schedule plan --kind claude-schedule` | the user (`/schedule`) |
| `on-request` | nothing runs by itself | — |

A scheduled run writes the digest into `laws/runs/<date>/` and its log into `laws/runs/schedule.log`; it sends
nothing. At the next conversation the agent reads the latest digest first, closes what stayed not verified if
the user wants, and reports. `watch schedule remove` uninstalls the launchd job.
