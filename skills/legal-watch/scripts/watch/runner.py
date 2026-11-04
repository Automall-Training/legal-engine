"""One monitoring run: every watched act against its official source → run.json, digest.md, state, snapshots,
and the contract clauses that depend on a changed act.

Rules (the engine's law-check discipline, `<legal-workflow>/references/law-check.md`):
- an act is *checked* only when the adapter read the version list (unchanged / new_in_force / new_future /
  repealed) with a parser calibrated on a live page of that source; anything else is "not verified", never
  "no changes";
- the first reading of an act records its baseline (`baseline`), it is not a change;
- a change read by an uncalibrated parser is reported as *possible*, does not move the baseline and asks for a
  check by hand (`legal_watch.py record`);
- one p1 act not verified → the run is INCOMPLETE (exit 2) and the digest never says "no changes";
- a future version is a change of kind `future`, never "in force".
Result and exit code: OK → 0, CHANGES → 1, INCOMPLETE → 2.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from . import clauses as _clauses
from . import digest as _digest
from . import library as lib
from .adapters import adapter_for, monitorul_md
from .contract import (FETCH_FAILED, NEW_FUTURE, NEW_IN_FORCE, PARSE_FAILED, REPEALED, SCAN_COMPLETE, UNCHANGED,
                       AdapterResult, ContractError)
from .fetchers import FetchResult, now_iso

BASELINE = "baseline"
VERIFIABLE = (UNCHANGED, NEW_IN_FORCE, NEW_FUTURE, REPEALED, BASELINE)
CHANGE_KIND = {NEW_IN_FORCE: "in_force", NEW_FUTURE: "future", REPEALED: "repealed"}
EXIT = {"OK": 0, "CHANGES": 1, "INCOMPLETE": 2}


class RecordingFetcher:
    """Keeps every page fetched in the run, so the official text can be saved as a snapshot."""

    def __init__(self, inner):
        self.inner = inner
        self.pages: dict[str, FetchResult] = {}

    def get(self, url: str) -> FetchResult:
        r = self.inner.get(url)
        self.pages[url] = r
        return r


def check_one(act: dict, fetcher, today: _dt.date) -> dict:
    name, fn = adapter_for(act)
    base = {"act_id": act["id"], "title": act.get("title"), "jurisdiction": act.get("jurisdiction"),
            "priority": act.get("priority")}
    if fn is None:
        kinds = sorted({s.get("kind") for s in act.get("sources") or []})
        res = AdapterResult(act_id=act["id"], adapter="none", status=FETCH_FAILED,
                            error=f"no monitoring source for this act (sources: {kinds or 'none'}); "
                                  "check it by hand and record the version card").to_dict()
        return {**base, **res, "reasons": ["no_source"]}
    try:
        res = fn(act, fetcher, today).to_dict()
    except ContractError as e:
        res = AdapterResult(act_id=act["id"], adapter=name, status=PARSE_FAILED,
                            error=f"adapter broke the result contract: {e}").to_dict()
        return {**base, **res, "reasons": ["adapter_crashed"]}
    except Exception as e:  # noqa: BLE001 — a crashed adapter is "not verified", never silence
        res = AdapterResult(act_id=act["id"], adapter=name, status=FETCH_FAILED,
                            error=f"adapter crashed: {type(e).__name__}: {str(e)[:200]}").to_dict()
        return {**base, **res, "reasons": ["adapter_crashed"]}
    return {**base, **res, "reasons": []}


def classify_record(r: dict) -> dict:
    """Effective status and the reasons an act is not verified (in place)."""
    st, notes = r["status"], r.get("notes") or []
    reasons = r.setdefault("reasons", [])
    if st == NEW_IN_FORCE and any(n.startswith("baseline absent") for n in notes):
        r["adapter_status"], r["status"] = st, BASELINE
    elif st not in VERIFIABLE and not reasons:
        reasons.append(st)
    ev = r.get("evidence") or {}
    if r["status"] in VERIFIABLE and not ev.get("parser_calibrated"):
        reasons.append("parser_uncalibrated")
        if r["status"] in (UNCHANGED, BASELINE):
            r.setdefault("adapter_status", r["status"])
            r["status"] = PARSE_FAILED
            r["error"] = ("the parser of this source is not yet calibrated on a live page: the reading is not "
                          "accepted as a check; confirm the act by hand")
    r["checked"] = r["status"] in VERIFIABLE and not reasons
    return r


def change_of(r: dict, run_date: str) -> dict | None:
    st = r["status"]
    if st not in CHANGE_KIND:
        return None
    red = (r.get("next") if st == NEW_FUTURE else r.get("current")) or {}
    return {"act_id": r["act_id"], "title": r.get("title"), "priority": r.get("priority"),
            "kind": CHANGE_KIND[st], "label": red.get("label"), "in_force_from": red.get("in_force_from"),
            "confirmed": bool(r.get("checked")), "reasons": list(r.get("reasons") or []), "run_date": run_date}


def update_state(state: dict, r: dict, day: str, snapshot: str | None) -> None:
    """Move the baseline only on a checked reading: an unconfirmed change keeps being reported until confirmed."""
    if not r.get("checked"):
        return
    held = state["acts"].setdefault(r["act_id"], {})
    if r["status"] == REPEALED:
        held["repealed"] = r.get("current")
    else:
        held["current"] = r.get("current")
        held["next"] = r.get("next")
    ev = r.get("evidence") or {}
    held.update({"sha256": ev.get("sha256"), "url": ev.get("url"), "via": ev.get("via"),
                 "checked_on": day, "snapshot": snapshot or held.get("snapshot")})


def finish(profile: Path, out: dict, state: dict, *, dry_run: bool) -> dict:
    """Shared tail of `run` and `record`: result, exit code, contract flags, digest, files."""
    records = out["acts"]
    unverified = [{"act_id": r["act_id"], "title": r.get("title"), "priority": r.get("priority"),
                   "status": r["status"], "reasons": list(r.get("reasons") or []) or [r["status"]],
                   "error": r.get("error")} for r in records if not r.get("checked")]
    mon = out.get("monitorul")
    if mon is not None and mon.get("status") != SCAN_COMPLETE:
        unverified.append({"act_id": "monitorul_md", "title": "Monitorul Oficial (MD)", "priority": "p2",
                           "status": mon.get("status"), "reasons": ["gazette_scan_incomplete"],
                           "error": mon.get("error")})
    changes = [c for c in (change_of(r, out["date"]) for r in records) if c]
    if any(u["priority"] == "p1" for u in unverified):
        result = "INCOMPLETE"
    elif changes:
        result = "CHANGES"
    else:
        result = "OK"
    out.update({"result": result, "exit_code": EXIT[result], "phrase_no_changes_allowed": result == "OK",
                "changes": changes, "unverified": unverified,
                "summary": {"acts": len(records), "checked": sum(bool(r.get("checked")) for r in records),
                            "baselines": sum(r["status"] == BASELINE for r in records),
                            "unverified": len(unverified),
                            "unverified_p1": sum(u["priority"] == "p1" for u in unverified),
                            "changes": len(changes)}})
    flagged = []
    if not dry_run:
        flagged = _clauses.flag_changes(profile, [c for c in changes if c["confirmed"]])
    out["contracts_to_review"] = flagged
    if not dry_run:
        runs = [x for x in state["runs"] if x.get("date") != out["date"]]
        state["runs"] = runs + [{"date": out["date"], "result": result, "at": now_iso()}]
        lib.save_state(profile, state)
    out["health"] = _digest.health(state, _dt.date.fromisoformat(out["date"]), out.get("schedule"))
    run_dir = lib.laws_dir(profile) / "runs" / out["date"]
    lib.write_json(run_dir / "run.json", out)
    lib.write_atomic(run_dir / "digest.md", _digest.render(out, out.get("language", "en")))
    return out


def run(profile: Path, acts: list[dict], fetcher, today: _dt.date, *, selector: str = "all",
        dry_run: bool = False, language: str = "en", schedule: str | None = None, scan_gazette: bool = True,
        mode: str = "live") -> dict:
    day = today.isoformat()
    state = lib.load_state(profile)
    chosen = lib.select(acts, selector)
    rec = RecordingFetcher(fetcher)
    records = []
    for act in chosen:
        r = classify_record(check_one(act, rec, today))
        snap = None
        ev = r.get("evidence") or {}
        page = rec.pages.get(ev.get("url") or "")
        if r.get("checked") and page is not None and not dry_run:
            snap = lib.save_snapshot(profile, r["act_id"], page.text or page.markdown, ev.get("sha256"), day)
        r["snapshot"] = snap
        if not dry_run:
            update_state(state, r, day, snap)
        records.append(r)

    mon = None
    md_acts = [a for a in chosen if a.get("jurisdiction") == "MD"]
    if scan_gazette and md_acts:
        since = (state.get("monitorul") or {}).get("checked_through")
        try:
            mon = monitorul_md.scan(md_acts, rec, since, today).to_dict()
        except Exception as e:  # noqa: BLE001
            mon = {"source": "monitorul_md", "status": FETCH_FAILED, "checked_through": since,
                   "previous_checked_through": since, "latest_seen": None, "editions": [], "signals": [],
                   "evidence": None, "error": f"scan crashed: {type(e).__name__}: {str(e)[:200]}"}
        if not dry_run and mon.get("checked_through") is not None:
            state["monitorul"] = {"checked_through": mon["checked_through"], "updated": day}

    out = {"schema_version": 1, "date": day, "generated_at": now_iso(), "mode": mode, "dry_run": dry_run,
           "selector": selector, "language": language, "schedule": schedule, "acts": records, "monitorul": mon}
    return finish(profile, out, state, dry_run=dry_run)
