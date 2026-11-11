"""Scheduled monitoring: a weekly local job (launchd on macOS, Task Scheduler on Windows, cron elsewhere) or a
Claude scheduled task.

Nothing is installed silently: `plan` only shows what would run; `install` writes the launchd job or creates the
Windows task after the user agreed in chat; cron and Claude tasks are printed for the user to add, because
editing someone's crontab or cloud tasks is their act.
"""
from __future__ import annotations

import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path

from . import library as lib

LABEL = "com.legal-engine.watch"
WEEKDAY, HOUR, MINUTE = 1, 9, 0          # Monday 09:00 local time: the Gazettes of the week before are out
KINDS = ("launchd", "cron", "claude-schedule", "schtasks")
TASK_NAME = "legal-engine-watch"         # the Windows task (Task Scheduler library root, current user)
SCHTASKS_TR_MAX = 261                    # schtasks refuses a longer /TR command
BY_HAND = {"cron": "remove the line with `crontab -e`", "claude-schedule": "delete the task in /schedule"}
# why: one switch for "this is Windows", so tests can flip it without patching os.name (pathlib reads os.name).
WINDOWS = os.name == "nt"


def default_kind(platform: str | None = None) -> str:
    """The local scheduler of this system, the CLI default (launchd was the default everywhere before 1.2.0)."""
    platform = sys.platform if platform is None else platform
    return "launchd" if platform == "darwin" else "schtasks" if platform == "win32" else "cron"


def venv_python(root: Path, windows: bool | None = None) -> Path:
    """The engine's Python inside `<root>/.venv` (Scripts\\python.exe on Windows, bin/python elsewhere).
    why: a copy of `legal-contracts/scripts/_engine_env.venv_python`, so this package imports nothing from another
    skill; tools/tests/test_platform.py checks that both give the same answer."""
    windows = WINDOWS if windows is None else windows
    return root / ".venv" / ("Scripts" if windows else "bin") / ("python.exe" if windows else "python")


def engine_python() -> Path:
    venv = venv_python(lib.SKILL.parents[1])
    return venv if venv.exists() else Path(sys.executable)


def command(profile: Path) -> list[str]:
    return [str(engine_python()), str(lib.SKILL / "scripts" / "legal_watch.py"), "--profile", str(profile), "run"]


def plist(profile: Path) -> bytes:
    log = str(lib.laws_dir(profile) / "runs" / "schedule.log")
    return plistlib.dumps({
        "Label": LABEL, "ProgramArguments": command(profile),
        "StartCalendarInterval": {"Weekday": WEEKDAY, "Hour": HOUR, "Minute": MINUTE},
        "StandardOutPath": log, "StandardErrorPath": log, "RunAtLoad": False})


def schtasks_create(profile: Path) -> list[str]:
    """The `schtasks /Create` call: weekly, Monday 09:00, as the current user (no admin rights); `/F` replaces an
    earlier task of the same name, so re-running never duplicates it.
    why: no `>> schedule.log` here (that needs `cmd /c` and makes the command too long for /TR); every run still
    writes run.json and the digest into laws/runs/<date>/, and Task Scheduler keeps the last exit code."""
    tr = subprocess.list2cmdline(command(profile))
    if len(tr) > SCHTASKS_TR_MAX:
        raise lib.WatchError(f"the task command is {len(tr)} characters, Task Scheduler takes {SCHTASKS_TR_MAX} at "
                             "most: move the engine or the profile to a shorter folder, or use claude-schedule")
    return ["schtasks", "/Create", "/TN", TASK_NAME, "/SC", "WEEKLY", "/D", "MON",
            "/ST", f"{HOUR:02d}:{MINUTE:02d}", "/TR", tr, "/F"]


def plan(profile: Path, kind: str) -> dict:
    if kind not in KINDS:
        raise lib.WatchError(f"schedule kind must be one of {list(KINDS)}")
    if kind == "schtasks":
        # why: list2cmdline is how Python hands the list to Windows, so this is exactly what `install` runs.
        return {"kind": kind, "task": TASK_NAME, "when": "every Monday 09:00",
                "command": subprocess.list2cmdline(schtasks_create(profile)),
                "how": "`watch schedule install --kind schtasks` runs this command, only after the user's yes"}
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


def install(profile: Path, kind: str = "launchd", *, run=subprocess.run, home: Path | None = None) -> dict:
    """Install the weekly job: launchd (macOS) or a Task Scheduler task (Windows). Re-running replaces the job,
    never duplicates it. Called only after the user's yes in chat."""
    if kind == "schtasks":
        return _install_schtasks(profile, run=run)
    if kind != "launchd":
        raise lib.WatchError(f"install handles launchd and schtasks only; for {kind} use `schedule plan --kind {kind}`")
    if sys.platform != "darwin":
        raise lib.WatchError(f"launchd exists only on macOS; use `schedule plan --kind {default_kind()}` instead")
    path = (home or Path.home()) / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    path.parent.mkdir(parents=True, exist_ok=True)
    (lib.laws_dir(profile) / "runs").mkdir(parents=True, exist_ok=True)
    run(["launchctl", "unload", str(path)], capture_output=True)   # absent job: harmless error, ignored
    path.write_bytes(plist(profile))
    p = run(["launchctl", "load", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise lib.WatchError(f"launchctl load failed (exit {p.returncode}): {p.stderr.strip()[:200]}")
    return {"installed": str(path), "when": "every Monday 09:00"}


def _schtasks(args: list[str], run) -> subprocess.CompletedProcess:
    # why: schtasks prints in the console code page, not UTF-8; errors="replace" keeps a localized message readable
    return run(args, capture_output=True, text=True, errors="replace")


def _install_schtasks(profile: Path, *, run) -> dict:
    if sys.platform != "win32":
        raise lib.WatchError(f"Task Scheduler (schtasks) exists only on Windows; use `schedule plan --kind "
                             f"{default_kind()}` instead")
    (lib.laws_dir(profile) / "runs").mkdir(parents=True, exist_ok=True)
    p = _schtasks(schtasks_create(profile), run)
    if p.returncode != 0:
        raise lib.WatchError(f"schtasks /Create failed (exit {p.returncode}): {(p.stderr or p.stdout).strip()[:200]}")
    return {"installed": f"Task Scheduler: {TASK_NAME}", "when": "every Monday 09:00"}


def remove(kind: str = "launchd", *, run=subprocess.run, home: Path | None = None) -> dict:
    if kind in BY_HAND:
        return {"removed": None, "how": BY_HAND[kind]}
    if kind == "schtasks":
        if sys.platform != "win32":
            raise lib.WatchError("Task Scheduler (schtasks) exists only on Windows")
        if _schtasks(["schtasks", "/Query", "/TN", TASK_NAME], run).returncode != 0:
            return {"removed": None}     # no such task: nothing to remove
        p = _schtasks(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], run)
        if p.returncode != 0:
            raise lib.WatchError(f"schtasks /Delete failed (exit {p.returncode}): "
                                 f"{(p.stderr or p.stdout).strip()[:200]}")
        return {"removed": f"Task Scheduler: {TASK_NAME}"}
    if kind != "launchd":
        raise lib.WatchError(f"schedule kind must be one of {list(KINDS)}")
    path = (home or Path.home()) / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    if not path.exists():
        return {"removed": None}
    run(["launchctl", "unload", str(path)], capture_output=True)
    path.unlink()
    return {"removed": str(path)}
