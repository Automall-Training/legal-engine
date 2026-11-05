"""The error log of monitoring (`<profile>/laws/issues.json`): what could not be read, since when, how often, and
what to do about it. The next run reads it (engines that a site keeps refusing go last), the agent follows the
recipe of each open issue (`references/issues.md`), and the person sees it on `laws/report.html`.

Two parts:
- `acts`: one entry per act that was not verified. It stays open until the act is checked (by a run or by a
  check by hand); a run of the same day never wipes the detail of an earlier failure, because every attempt is
  appended to `history`.
- `engines`: per site and engine, how many runs in a row the engine failed there. After `DEMOTE_AFTER` runs it is
  tried last for that site (it still runs when it is the only engine: a skipped site would be silence); every
  `RETRY_FIRST_DAYS` days it is tried first again, in case the site opened up.

Nothing here ever turns a failure into "no changes": the log only remembers and routes.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from urllib.parse import urlparse

from . import library as lib

SCHEMA = 1
DEMOTE_AFTER = 3
RETRY_FIRST_DAYS = 7
KEEP_RESOLVED_DAYS = 90
HISTORY = 10
ERROR_MAX = 300

# A reason (runner.classify_record) → the issue kind and the recipe the agent follows (references/issues.md).
KIND = {"blocked_403": "blocked", "fetch_failed": "fetch_failed", "parse_failed": "parse_failed",
        "parser_uncalibrated": "uncalibrated", "no_source": "no_source", "stale_fallback": "stale_fallback",
        "adapter_crashed": "reader_crashed", "gazette_scan_incomplete": "gazette_failed"}
# Not reading errors: the user chose hand checks, or the Gazette is ahead of the consolidated page. The digest
# lists them; the log would only fill up with expected work.
NOT_ERRORS = {"host_only", "gazette_signal"}


def path(profile: Path) -> Path:
    return lib.laws_dir(profile) / "issues.json"


def empty() -> dict:
    return {"schema_version": SCHEMA, "acts": {}, "engines": {}}


def load(profile: Path) -> dict:
    p = path(profile)
    if not p.exists():
        return empty()
    data = lib.read_json(p, "monitoring error log")
    if data.get("schema_version") != SCHEMA:
        raise lib.WatchError(f"error log {p} has schema {data.get('schema_version')!r}, expected {SCHEMA}")
    data.setdefault("acts", {})
    data.setdefault("engines", {})
    _validate(data, p)
    return data


def _is_date(x, *, optional: bool = True) -> bool:
    if x is None:
        return optional
    try:
        _dt.date.fromisoformat(x)
        return True
    except (TypeError, ValueError):
        return False


def _act_ok(e) -> bool:
    if not isinstance(e, dict) or e.get("state") not in ("open", "resolved"):
        return False
    if not all(isinstance(e.get(k, 0), int) and not isinstance(e.get(k, 0), bool) for k in ("count", "streak")):
        return False
    if not isinstance(e.get("history", []), list) or not all(isinstance(h, dict) for h in e.get("history", [])):
        return False
    if e.get("last") is not None and not isinstance(e["last"], dict):
        return False
    if not all(_is_date(e.get(k)) for k in ("first_seen", "last_seen", "resolved_on")):
        return False
    return all(e.get(k) is None or isinstance(e[k], str) for k in ("act_id", "kind", "title", "priority", "host"))


def _engine_ok(v) -> bool:
    return (isinstance(v, dict) and isinstance(v.get("streak", 0), int) and not isinstance(v.get("streak", 0), bool)
            and all(_is_date(v.get(k)) for k in ("demoted_since", "last_failed", "last_ok")))


def _validate(data: dict, p: Path) -> None:
    """A hand-edited or damaged log is a clear error before any write, not a crash in the middle of a run: every
    field that the update, the sorting and the page read is checked here."""
    bad = []
    if not isinstance(data["acts"], dict) or not isinstance(data["engines"], dict):
        bad.append("acts and engines must be objects")
    else:
        bad += [f"acts.{k}" for k, e in data["acts"].items() if not _act_ok(e)]
        for h, eng in data["engines"].items():
            if not isinstance(eng, dict):
                bad.append(f"engines.{h}")
            else:
                bad += [f"engines.{h}.{v}" for v, e in eng.items() if not _engine_ok(e)]
    if not bad:
        # why: the key is the identity; the redundant fields every consumer reads are filled from it and defaults
        for k, e in data["acts"].items():
            e["act_id"] = k
            for f, v in (("count", 0), ("streak", 0), ("history", [])):
                e.setdefault(f, v)
        for eng in data["engines"].values():
            for e in eng.values():
                e.setdefault("streak", 0)
                e.setdefault("demoted_since", None)
        return
    if bad:
        raise lib.WatchError(f"error log {p} is damaged ({', '.join(bad[:5])}); move it away and run again "
                             "(the next run starts a new log)")


def save(profile: Path, log: dict) -> None:
    lib.write_json(path(profile), log)


def host_of(url: str | None) -> str | None:
    return urlparse(url or "").hostname or None


def kind_of(reasons: list[str]) -> str | None:
    """The issue kind of an unverified act: the first reason that is a reading error."""
    for r in reasons:
        if r in NOT_ERRORS:
            continue
        return KIND.get(r, r)   # why: a new status still gets logged, under its own code
    return None


def _days(a: str, b: str) -> int:
    return (_dt.date.fromisoformat(b) - _dt.date.fromisoformat(a)).days


def update_acts(log: dict, unverified: list[dict], checked_ids: set[str], day: str, at: str, *,
                resolved_by: str = "checked by a run") -> None:
    """One attempt per act read now: failures are appended, a checked act closes its issue."""
    acts = log["acts"]
    for u in unverified:
        kind = kind_of(u.get("reasons") or [u.get("status")])
        if kind is None:
            continue
        entry = acts.get(u["act_id"])
        if entry is None or entry.get("state") != "open":
            entry = {"act_id": u["act_id"], "first_seen": day, "count": 0, "streak": 0, "history": []}
            acts[u["act_id"]] = entry
        attempt = {"date": day, "at": at, "kind": kind, "status": u.get("status"), "via": u.get("via"),
                   "url": u.get("url"), "http_status": u.get("http_status"),
                   "error": (u.get("error") or "")[:ERROR_MAX] or None, "notes": list(u.get("notes") or [])[:5]}
        entry.update({"title": u.get("title"), "priority": u.get("priority"), "kind": kind, "state": "open",
                      "host": host_of(u.get("url")) or entry.get("host"), "last_seen": day,
                      "count": entry["count"] + 1, "streak": entry["streak"] + 1, "last": attempt,
                      "fix": kind, "resolved_on": None, "resolved_by": None})
        entry["history"] = (entry["history"] + [attempt])[-HISTORY:]
    for act_id in checked_ids:
        entry = acts.get(act_id)
        if entry and entry.get("state") == "open":
            entry.update({"state": "resolved", "resolved_on": day, "streak": 0, "resolved_by": resolved_by})
    for act_id in [k for k, e in acts.items() if e.get("state") == "resolved"
                   and _days(e.get("resolved_on") or day, day) > KEEP_RESOLVED_DAYS]:
        del acts[act_id]


def update_engines(log: dict, attempts: list[dict], day: str) -> None:
    """Per site and engine: a run where every attempt failed adds one to the streak; one success resets it."""
    runs: dict[tuple[str, str], dict] = {}
    for a in attempts:
        if not a.get("host") or not a.get("via"):
            continue
        r = runs.setdefault((a["host"], a["via"]), {"ok": 0, "failed": 0, "error": None})
        if a.get("ok"):
            r["ok"] += 1
        else:
            r["failed"] += 1
            r["error"] = (a.get("error") or "")[:ERROR_MAX] or None
    for (host, via), r in runs.items():
        e = log["engines"].setdefault(host, {}).setdefault(via, {"streak": 0, "demoted_since": None})
        if r["ok"]:
            e.update({"streak": 0, "demoted_since": None, "last_ok": day})
            continue
        if e.get("last_failed") != day:   # why: several runs on one day are one day of refusals, not three
            e["streak"] += 1
        e.update({"last_failed": day, "last_error": r["error"]})
        if e["streak"] >= DEMOTE_AFTER and (e.get("demoted_since") is None
                                            or _days(e["demoted_since"], day) >= RETRY_FIRST_DAYS):
            e["demoted_since"] = day


def demoted(log: dict, today: _dt.date) -> dict[str, set[str]]:
    """Site → engines to try last today."""
    out: dict[str, set[str]] = {}
    for host, engines in (log.get("engines") or {}).items():
        for via, e in engines.items():
            since = e.get("demoted_since")
            if e.get("streak", 0) >= DEMOTE_AFTER and since and (today - _dt.date.fromisoformat(since)).days \
                    < RETRY_FIRST_DAYS:
                out.setdefault(host, set()).add(via)
    return out


def open_issues(log: dict) -> list[dict]:
    order = {"p1": 0, "p2": 1, "p3": 2}
    return sorted((e for e in log["acts"].values() if e.get("state") == "open"),
                  key=lambda e: (order.get(e.get("priority"), 9), -e.get("streak", 0), e["act_id"]))


def site_issues(log: dict) -> list[dict]:
    """Engines that failed on a site in at least one run in a row, worst first."""
    out = [{"host": h, "via": v, **e} for h, eng in (log.get("engines") or {}).items() for v, e in eng.items()
           if e.get("streak", 0) > 0]
    return sorted(out, key=lambda e: (-e["streak"], e["host"], e["via"]))


def prepare_run(profile: Path, out: dict, read_ids: set[str], *, by_hand: bool = False,
                watched: set[str] | None = None) -> dict:
    """Update the log from what was read now (not the merged day) and the engine attempts of this run.

    `read_ids`: the acts read now, plus "monitorul_md" when the Gazette was scanned now.
    `watched`: the whole current watchlist (not the acts of a partial run), plus "monitorul_md" while a Moldovan act
    is watched: an open problem of an act the user removed (or of the Gazette, once no Moldovan act is left) is
    closed as "removed from the watchlist", since no recipe can reach it.
    """
    log = load(profile)
    day, at = out["date"], out.get("generated_at") or out["date"]
    unverified = [u for u in out.get("unverified") or [] if u["act_id"] in read_ids]
    checked = {r["act_id"] for r in out.get("acts") or [] if r["act_id"] in read_ids and r.get("checked")}
    if "monitorul_md" in read_ids and not any(u["act_id"] == "monitorul_md" for u in unverified):
        checked.add("monitorul_md")
    update_acts(log, unverified, checked, day, at, resolved_by="checked by hand" if by_hand else "checked by a run")
    update_engines(log, out.get("engine_attempts") or [], day)
    if watched is not None:
        for act_id, e in log["acts"].items():
            if e.get("state") == "open" and act_id not in watched:
                e.update({"state": "resolved", "resolved_on": day, "streak": 0,
                          "resolved_by": "removed from the watchlist"})
    return log


def record_run(profile: Path, out: dict, read_ids: set[str], *, by_hand: bool = False,
               watched: set[str] | None = None) -> dict:
    log = prepare_run(profile, out, read_ids, by_hand=by_hand, watched=watched)
    save(profile, log)
    return log
