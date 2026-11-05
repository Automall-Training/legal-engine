#!/usr/bin/env python3
"""legal-watch: law library, monitoring and contract re-review. Run with the engine's .venv/bin/python.

    legal_watch.py catalog [niches|categories|acts] [--countries MD,RO,EU]
    legal_watch.py suggest --niches a,b [--b2c] [--countries MD,RO,EU]
    legal_watch.py init --niches a,b --categories c,d [--acts p1|all|id,…] [--add id,…] [--b2c]
                        [--countries …] [--language ru|ro|en] [--engines urllib,playwright,command,host]
                        [--fetch-command CMD] [--schedule on-request|weekly|claude-schedule] [--force]
    legal_watch.py show
    legal_watch.py run [--acts all|p1|id,…] [--today YYYY-MM-DD] [--dry-run] [--no-gazette]
    legal_watch.py record --card <version-card.json> [--root <matter>]
    legal_watch.py digest [--date YYYY-MM-DD]
    legal_watch.py index scan <contract> --jurisdiction MD|RO [--write] [--force]
    legal_watch.py index check | pending
    legal_watch.py index clear --contract <file> [--clause N] --matter <matter-id>
    legal_watch.py schedule plan|install|remove [--kind launchd|cron|claude-schedule]

Global: --profile <dir> (default: the profile of legal-workflow's config.json).
Exit codes: 0 ok (run: OK), 1 run: CHANGES / check: errors, 2 bad input or run: INCOMPLETE, 3 unexpected error.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from watch import clauses, library as lib, manual, runner, schedule  # noqa: E402
from watch.fetchers import BrowserBusy, FetchConfigError, HostOnly, build_chain  # noqa: E402

WORKFLOW_SCRIPTS = lib.SKILL.parent / "legal-workflow" / "scripts"


def resolve_profile(raw: str | None) -> Path:
    if raw:
        path = Path(raw).expanduser()
        lib.refuse_engine(path / "laws")
        return path
    sys.path.insert(0, str(WORKFLOW_SCRIPTS))
    try:
        import legal_profile
        return legal_profile.resolve_profile()[0]
    except ImportError as e:
        raise lib.WatchError("legal-workflow is not installed next to legal-watch; pass --profile") from e
    except Exception as e:  # noqa: BLE001 — the profile script raises its own typed errors
        raise lib.WatchError(f"cannot find the profile: {e}") from e


def _csv(s: str | None) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _watch(profile: Path):
    wl = lib.load_watchlist(lib.laws_dir(profile) / "watchlist.yaml")
    catalog, _ = lib.load_catalog()
    acts = lib.resolve_acts(wl, catalog, lib.load_state(profile))
    return wl, acts


def cmd_catalog(a) -> int:
    acts, niches = lib.load_catalog()
    countries = set(_csv(a.countries) or lib.JURISDICTIONS)
    if a.what == "niches":
        _print({k: v["label"] for k, v in niches["niches"].items()})
    elif a.what == "categories":
        _print({k: v["label"] for k, v in niches["categories"].items()})
    else:
        _print([{k: x.get(k) for k in ("id", "title", "jurisdiction", "priority", "status", "checked_on")}
                for x in acts.values() if x["jurisdiction"] in countries])
    return 0


def cmd_suggest(a) -> int:
    acts, niches = lib.load_catalog()
    _print(lib.suggest(niches, acts, _csv(a.niches), b2c=a.b2c, countries=_csv(a.countries) or list(lib.JURISDICTIONS)))
    return 0


def cmd_init(a) -> int:
    profile = resolve_profile(a.profile)
    path = lib.laws_dir(profile) / "watchlist.yaml"
    if path.exists() and not a.force:
        raise lib.WatchError(f"{path} exists; re-run with --force to replace it (the state and texts are kept)")
    acts, niches = lib.load_catalog()
    countries = _csv(a.countries) or list(lib.JURISDICTIONS)
    sug = lib.suggest(niches, acts, _csv(a.niches), b2c=a.b2c, countries=countries)
    chosen_cats = _csv(a.categories) or [c["category"] for c in sug["categories"]]
    unknown = [c for c in chosen_cats if c not in niches["categories"]]
    if unknown:
        raise lib.WatchError(f"unknown categories: {', '.join(unknown)}")
    ids = list(dict.fromkeys(i for c in chosen_cats for i in niches["categories"][c]["acts"]
                             if i in acts and acts[i]["jurisdiction"] in countries))
    if a.acts == "p1":
        ids = [i for i in ids if acts[i].get("priority") == "p1"]
    elif a.acts != "all":
        # Chosen from the whole catalog (`catalog acts`), not only from the chosen categories.
        ids = [i for i in _csv(a.acts) if i != "none"]
    extra = [i for i in _csv(a.add) if i not in ids]
    unknown = [i for i in ids + extra if i not in acts]
    if unknown:
        raise lib.WatchError(f"not in the catalog: {', '.join(unknown)}; an own act is added to the watchlist by "
                             "hand with title, jurisdiction and sources (setup.md)")
    ids += extra
    data = {"schema_version": 1,
            "settings": {"countries": countries, "language": a.language, "engines": _csv(a.engines),
                         "fetch_command": a.fetch_command, "schedule": a.schedule},
            "niches": _csv(a.niches), "categories": chosen_cats, "acts": [{"id": i} for i in ids]}
    lib.validate_watchlist(json.loads(json.dumps(data)))
    lib.write_atomic(path, lib.dump_watchlist(data))
    _print({"watchlist": str(path), "acts": len(ids), "categories": chosen_cats})
    return 0


def cmd_show(a) -> int:
    profile = resolve_profile(a.profile)
    wl, acts = _watch(profile)
    state = lib.load_state(profile)
    _print({"settings": wl["settings"], "acts": [
        {"id": x["id"], "priority": x.get("priority"), "held": (x.get("current") or {}).get("label"),
         "checked_on": (state["acts"].get(x["id"]) or {}).get("checked_on")} for x in acts],
        "last_runs": state["runs"][-5:], "contracts_to_review": clauses.pending(profile)})
    return 0


def cmd_run(a) -> int:
    profile = resolve_profile(a.profile)
    wl, acts = _watch(profile)
    s = wl["settings"]
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    engines = [e for e in s["engines"] if e != "host"]
    with contextlib.ExitStack() as stack:
        if engines:
            fetcher = build_chain(engines, command=s.get("fetch_command"),
                                  browser_dir=lib.laws_dir(profile) / ".browser", stack=stack)
        else:  # host only: nothing is fetched; every act is listed for the agent to check by hand
            fetcher = HostOnly()
        out = runner.run(profile, acts, fetcher, today, selector=a.acts, dry_run=a.dry_run,
                         language=s["language"], schedule=s["schedule"], scan_gazette=not a.no_gazette and bool(engines),
                         direct_http="urllib" in engines, mode="live" if engines else "host")
    sm = out["summary"]
    print(f"{out['result']} · checked {sm['checked']}/{sm['acts']} · not verified (p1): {sm['unverified_p1']} · "
          f"changes: {sm['changes']} · {lib.laws_dir(profile) / 'runs' / out['date'] / 'digest.md'}")
    return out["exit_code"]


def cmd_record(a) -> int:
    profile = resolve_profile(a.profile)
    wl, acts = _watch(profile)
    out = manual.record(profile, acts, Path(a.card), dt.date.today(), root=Path(a.root) if a.root else None,
                        language=wl["settings"]["language"], schedule=wl["settings"]["schedule"])
    rec = next(x for x in out["acts"] if x["act_id"] == json.loads(Path(a.card).read_text())["act"]["id"])
    _print({"act": rec["act_id"], "status": rec["status"], "checked": rec["checked"], "result": out["result"]})
    return 0


def cmd_digest(a) -> int:
    profile = resolve_profile(a.profile)
    runs = lib.laws_dir(profile) / "runs"
    day = a.date
    if day is None and runs.exists():
        day = max((p.name for p in runs.iterdir() if (p / "digest.md").exists()), default=None)
    if not day or not (runs / day / "digest.md").exists():
        raise lib.WatchError("no digest yet: run `legal_watch.py run` first")
    print((runs / day / "digest.md").read_text(encoding="utf-8"))
    return 0


def cmd_index(a) -> int:
    profile = resolve_profile(a.profile)
    if a.op == "scan":
        if not a.contract or not a.jurisdiction:
            raise lib.WatchError("index scan needs <contract> and --jurisdiction MD|RO")
        catalog, _ = lib.load_catalog()
        draft = clauses.scan(Path(a.contract), a.jurisdiction, clauses.catalog_codes(catalog))
        if a.write:
            _print({"written": str(clauses.save(profile, draft, force=a.force)), "clauses": len(draft["clauses"])})
        else:
            _print(draft)
        return 0
    if a.op == "check":
        # Only watched acts reach a clause: an act merely in the catalog is never monitored.
        known = {x["id"] for x in lib.load_watchlist(lib.laws_dir(profile) / "watchlist.yaml")["acts"]}
        report = {p.name: clauses.validate(ix, known) for p, ix in clauses.load_all(profile).items()}
        _print(report)
        return 1 if any(report.values()) else 0
    if a.op == "pending":
        _print(clauses.pending(profile))
        return 0
    if not a.contract_name:
        raise lib.WatchError("index clear needs --contract")
    _print({"cleared": clauses.clear(profile, a.contract_name, a.clause, a.matter)})
    return 0


def cmd_schedule(a) -> int:
    profile = resolve_profile(a.profile)
    if a.op == "plan":
        _print(schedule.plan(profile, a.kind))
    elif a.op == "install":
        if a.kind != "launchd":
            raise lib.WatchError(f"install handles launchd only; for {a.kind} use `schedule plan --kind {a.kind}`")
        _print(schedule.install(profile))
    else:
        _print(schedule.remove())
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--profile")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("catalog")
    c.add_argument("what", nargs="?", default="niches", choices=("niches", "categories", "acts"))
    c.add_argument("--countries")
    s = sub.add_parser("suggest")
    s.add_argument("--niches", required=True)
    s.add_argument("--b2c", action="store_true")
    s.add_argument("--countries")
    i = sub.add_parser("init")
    i.add_argument("--niches", default="")
    i.add_argument("--categories")
    i.add_argument("--acts", default="all")
    i.add_argument("--add")
    i.add_argument("--b2c", action="store_true")
    i.add_argument("--countries")
    i.add_argument("--language", default="ru", choices=lib.LANGUAGES)
    i.add_argument("--engines", default="urllib,host")
    i.add_argument("--fetch-command")
    i.add_argument("--schedule", default="weekly", choices=lib.SCHEDULES)
    i.add_argument("--force", action="store_true")
    sub.add_parser("show")
    r = sub.add_parser("run")
    r.add_argument("--acts", default="all")
    r.add_argument("--today")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--no-gazette", action="store_true")
    rc = sub.add_parser("record")
    rc.add_argument("--card", required=True)
    rc.add_argument("--root")
    d = sub.add_parser("digest")
    d.add_argument("--date")
    x = sub.add_parser("index")
    x.add_argument("op", choices=("scan", "check", "pending", "clear"))
    x.add_argument("contract", nargs="?")
    x.add_argument("--jurisdiction", choices=("MD", "RO"))
    x.add_argument("--write", action="store_true")
    x.add_argument("--force", action="store_true")
    x.add_argument("--contract", dest="contract_name")
    x.add_argument("--clause")
    x.add_argument("--matter")
    sc = sub.add_parser("schedule")
    sc.add_argument("op", choices=("plan", "install", "remove"))
    sc.add_argument("--kind", default="launchd", choices=schedule.KINDS)
    return ap


COMMANDS = {"catalog": cmd_catalog, "suggest": cmd_suggest, "init": cmd_init, "show": cmd_show, "run": cmd_run,
            "record": cmd_record, "digest": cmd_digest, "index": cmd_index, "schedule": cmd_schedule}


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)
    try:
        return COMMANDS[a.cmd](a)
    except (lib.WatchError, FetchConfigError, BrowserBusy) as e:
        print(f"legal_watch: {e}", file=sys.stderr)
        return 2
    except ImportError as e:
        print(f"legal_watch: a package is missing ({e.name}); run with the engine's .venv/bin/python, and for the "
              "playwright engine install it with `WITH_PLAYWRIGHT=1 ./install.sh`", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 — exit 1 means "changes found": a crash must never look like it
        print(f"legal_watch: unexpected error {type(e).__name__}: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
