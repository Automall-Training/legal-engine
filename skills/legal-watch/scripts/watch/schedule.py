"""Scheduled monitoring: a weekly local job (launchd on macOS, cron elsewhere) or a Claude scheduled task.

Nothing is installed silently: `plan` only shows what would run; `install` writes the launchd job after the
user agreed in chat; cron and Claude tasks are printed for the user to add, because editing someone's crontab
or cloud tasks is their act.
"""
from __future__ import annotations

import plistlib
import shlex
import subprocess
import sys
from pathlib import Path

from . import library as lib

LABEL = "com.legal-engine.watch"
WEEKDAY, HOUR, MINUTE = 1, 9, 0          # Monday 09:00 local time: the Gazettes of the week before are out
KINDS = ("launchd", "cron", "claude-schedule")


def engine_python() -> Path:
    venv = lib.SKILL.parents[1] / ".venv" / "bin" / "python"
    return venv if venv.exists() else Path(sys.executable)


def command(profile: Path) -> list[str]:
    return [str(engine_python()), str(lib.SKILL / "scripts" / "legal_watch.py"), "--profile", str(profile), "run"]


def plist(profile: Path) -> bytes:
    log = str(lib.laws_dir(profile) / "runs" / "schedule.log")
    return plistlib.dumps({
        "Label": LABEL, "ProgramArguments": command(profile),
        "StartCalendarInterval": {"Weekday": WEEKDAY, "Hour": HOUR, "Minute": MINUTE},
        "StandardOutPath": log, "StandardErrorPath": log, "RunAtLoad": False})


def plan(profile: Path, kind: str) -> dict:
    if kind not in KINDS:
        raise lib.WatchError(f"schedule kind must be one of {list(KINDS)}")
    cmd = " ".join(shlex.quote(c) for c in command(profile))
    if kind == "launchd":
        return {"kind": kind, "file": str(Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"),
                "when": "every Monday 09:00", "command": cmd}
    if kind == "cron":
        return {"kind": kind, "line": f"{MINUTE} {HOUR} * * {WEEKDAY} {cmd} >> "
                                      f"{shlex.quote(str(lib.laws_dir(profile) / 'runs' / 'schedule.log'))} 2>&1",
                "how": "add the line with `crontab -e`"}
    return {"kind": kind, "how": "create a weekly Claude scheduled task (/schedule) with this prompt",
            "prompt": "Run the law monitoring of my legal profile (legal-watch, `legal_watch.py run`), then "
                      "check by hand every act it reports as not verified and give me the digest."}


def install(profile: Path, *, run=subprocess.run, home: Path | None = None) -> dict:
    """Write and load the launchd job (macOS only). Re-running replaces the job, never duplicates it."""
    if sys.platform != "darwin":
        raise lib.WatchError("launchd exists only on macOS; use `schedule plan --kind cron` instead")
    path = (home or Path.home()) / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    path.parent.mkdir(parents=True, exist_ok=True)
    (lib.laws_dir(profile) / "runs").mkdir(parents=True, exist_ok=True)
    run(["launchctl", "unload", str(path)], capture_output=True)   # absent job: harmless error, ignored
    path.write_bytes(plist(profile))
    p = run(["launchctl", "load", str(path)], capture_output=True, text=True)
    if p.returncode != 0:
        raise lib.WatchError(f"launchctl load failed (exit {p.returncode}): {p.stderr.strip()[:200]}")
    return {"installed": str(path), "when": "every Monday 09:00"}


def remove(*, run=subprocess.run, home: Path | None = None) -> dict:
    path = (home or Path.home()) / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    if not path.exists():
        return {"removed": None}
    run(["launchctl", "unload", str(path)], capture_output=True)
    path.unlink()
    return {"removed": str(path)}
