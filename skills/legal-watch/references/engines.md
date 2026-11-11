# Fetch engines and the schedule

## Engines (`settings.engines`, tried in order)

| Engine | Cost | What it needs | Honest limits |
|---|---|---|---|
| `urllib` | free | nothing (Python standard library) | several official portals block it or drop the connection: those acts end "not verified" |
| `playwright` | free | `WITH_PLAYWRIGHT=1 ./install.sh`, on Windows `$env:WITH_PLAYWRIGHT=1` then `install.ps1` (a local browser) | anti-bot pages are never bypassed; slower; the browser profile lives in `laws/.browser/` |
| `command` | the user's choice (for example a paid reading service) | `settings.fetch_command`: the user's own command with `{url}`, printing the page (HTML or markdown) to stdout; on Windows `{url}` becomes `"%LEGAL_WATCH_URL%"` and the URL is passed in that variable, so cmd.exe cannot change a `%…%` in it | the user sets up the service and its key themselves; the engine passes only the URL and never reads, asks for or stores a key |
| `host` | free | the agent in a conversation | not automatic: acts left not verified are checked by hand (monitoring.md, "Host check") |

When an engine fails on a page, the next one is tried; the run records which engine produced each reading
(`evidence.via`). The EU fallback to the Publications Office (Cellar) uses plain HTTP, so it runs only when
`urllib` is among the engines; with `host` alone, scripts open no page at all. Every engine sends GET requests
to public pages only, waits 5–15 s between pages, and never fills forms, logs in or solves a CAPTCHA.

## Schedule (`settings.schedule`)

| Choice | How | Who installs it |
|---|---|---|
| `weekly` (default) | every Monday 09:00 by the system's own scheduler, `watch schedule plan` shows it first: macOS a launchd job, Windows a Task Scheduler task (`schtasks`, as the current user, no admin rights), Linux a cron line. `--kind` picks another one | launchd and schtasks: `watch schedule install`, only after the user's explicit yes in chat; cron: the user, with `crontab -e` |
| `claude-schedule` | a weekly Claude scheduled task with the prompt from `watch schedule plan --kind claude-schedule` | the user (`/schedule`) |
| `on-request` | nothing runs by itself | — |

A scheduled run writes the digest into `laws/runs/<date>/` and its log into `laws/runs/schedule.log`; it sends
nothing. At the next conversation the agent reads the latest digest first, closes what stayed not verified if
the user wants, and reports. `watch schedule remove` uninstalls the launchd job or the Windows task. The Windows
task writes no `schedule.log` (Task Scheduler limits its command to 261 characters; `plan` refuses a longer one and
says to use a shorter folder); its run still leaves `run.json` and the digest, and Task Scheduler shows the last
result.
