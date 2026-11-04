"""The `host` engine: an act checked by hand by the agent becomes a monitoring result.

When no script engine can read an official page (anti-bot pages, a portal that drops connections), the agent
opens it with its own web tools or the user's browser and fills a version card of `legal-research`
(`<legal-research>/references/version-check.md`). `record` validates the card with that skill's checker, turns it
into an `AdapterResult` of adapter `host` and merges it into today's run: the same comparison with the held
baseline, the same state, digest and contract flags as an automatic reading. A card that is not from today, fails
the checker or is `not_verified` changes nothing.
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
from pathlib import Path

from . import library as lib
from . import runner
from .contract import AdapterResult, Evidence, Redaction, classify, parse_date

CHECKER = lib.SKILL.parent / "legal-research" / "scripts" / "check_version.py"


def _checker():
    if not CHECKER.exists():
        raise lib.WatchError(f"legal-research is not installed next to legal-watch ({CHECKER} missing)")
    spec = importlib.util.spec_from_file_location("check_version", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def card_to_result(act: dict, card: dict, today: _dt.date) -> AdapterResult:
    """A version card that passed the checker → the monitoring result for the act."""
    if (card.get("act") or {}).get("id") != act["id"]:
        raise lib.WatchError(f"the card is for {(card.get('act') or {}).get('id')!r}, not {act['id']}")
    if card.get("result") not in ("current", "outdated"):
        raise lib.WatchError("a not_verified card changes nothing: the act stays not verified in this run")
    latest = card.get("latest_in_force") or {}
    parsed = []
    if latest.get("version_from"):
        parsed.append(Redaction(label=latest.get("label") or f"version from {latest['version_from']}",
                                in_force_from=latest["version_from"]))
    for nxt in card.get("next_versions") or []:
        parsed.append(Redaction(label=nxt.get("label") or f"version from {nxt['applies_from']}",
                                in_force_from=nxt["applies_from"]))
    rep = card.get("repealed") or {}
    gone = bool(rep.get("from")) and parse_date(rep["from"]) <= today
    if rep.get("from") and not gone:
        # A repeal dated in the future is a next version of the act, not a repeal today.
        parsed.append(Redaction(label=f"repeal by {rep.get('by')}", in_force_from=rep["from"]))
    ev_list = ((card.get("points") or {}).get("consolidation") or {}).get("evidence") or []
    ev0 = ev_list[0] if ev_list else {}
    sha = ev0.get("text_sha256") or (card.get("held_version") or {}).get("sha256")
    evidence = Evidence(url=ev0.get("url") or (card.get("act") or {}).get("official_record_url") or "",
                        fetched_at=card.get("checked_at") or "", sha256=sha, parser="version-card",
                        parser_calibrated=True, via="host")
    status, cur, nxt, err, notes = classify(act=act, parsed=parsed, today=today, repealed=gone,
                                            repealed_label=f"repealed by {rep.get('by')}" if gone else None)
    if status == "unchanged" and not sha:
        # The contract needs a hash for "unchanged": the agent saves the text it read (text_file + text_sha256).
        status, err = "parse_failed", "the card has no text_sha256 of the text read: save the text and give its hash"
    notes = ["checked by hand from a version card"] + notes
    return AdapterResult(act_id=act["id"], adapter="host", status=status, current=cur, next=nxt,
                         evidence=evidence, error=err, notes=notes).validate()


def record(profile: Path, acts: list[dict], card_path: Path, today: _dt.date, *, root: Path | None = None,
           language: str = "en", schedule: str | None = None) -> dict:
    checker = _checker()
    card = checker.load(Path(card_path))
    check = checker.validate(card, _dt.datetime.now().astimezone(), root)
    if check["errors"]:
        raise lib.WatchError("the version card fails its checker: " + "; ".join(check["errors"]))
    act_id = (card.get("act") or {}).get("id")
    act = next((a for a in acts if a["id"] == act_id), None)
    if act is None:
        raise lib.WatchError(f"{act_id!r} is not in the watchlist; add it first")
    res = card_to_result(act, card, today).to_dict()
    r = runner.classify_record({"act_id": act["id"], "title": act.get("title"),
                                "jurisdiction": act.get("jurisdiction"), "priority": act.get("priority"),
                                **res, "reasons": []})
    state = lib.load_state(profile)
    text_file = ((card.get("points") or {}).get("consolidation") or {}).get("evidence", [{}])[0].get("text_file")
    snap = None
    if r.get("checked") and text_file and root is not None and (Path(root) / text_file).is_file():
        text = (Path(root) / text_file).read_text(encoding="utf-8", errors="replace")
        snap = lib.save_snapshot(profile, act["id"], text, (r.get("evidence") or {}).get("sha256"), today.isoformat())
    r["snapshot"] = snap
    runner.update_state(state, r, today.isoformat(), snap)

    run_path = lib.laws_dir(profile) / "runs" / today.isoformat() / "run.json"
    if run_path.exists():
        out = lib.read_json(run_path, "run of today")
        out["acts"] = [x for x in out["acts"] if x["act_id"] != act["id"]] + [r]
    else:
        out = {"schema_version": 1, "date": today.isoformat(), "generated_at": runner.now_iso(), "mode": "host",
               "dry_run": False, "selector": act["id"], "language": language, "schedule": schedule,
               "acts": [r], "monitorul": None}
    return runner.finish(profile, out, state, dry_run=False)
