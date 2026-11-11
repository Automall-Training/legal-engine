#!/usr/bin/env python3
"""Trademark deadlines from the user's portfolio: raw dates, each with its rule and "check on the task date".

The rules live in ``assets/deadline-rules.json`` and are navigation, not law: a date is printed with the article
it comes from and a status (``reported`` or ``not-read``), never as verified. The portfolio lives in the user's
profile (``<profile>/trademarks/portfolio.json``), never in the engine.

Commands:
  rules                                   list the rules
  compute --rule ID --date YYYY-MM-DD     one deadline from one event
  portfolio --file PATH [--today D] [--horizon-days N] [--all]
                                          deadlines of every mark, nearest first

Exit codes: 0 done, 2 bad input (the message names the file, mark or field).
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import sys
from pathlib import Path

RULES_FILE = Path(__file__).resolve().parent.parent / "assets" / "deadline-rules.json"
SCHEMA_VERSION = 1
OFFICES = {"AGEPI", "OSIM", "EUIPO", "WIPO"}
STATUSES = {"planned", "filed", "published", "admitted", "registered", "refused", "withdrawn", "expired"}
EVENTS = ("filed_on", "published_on", "admission_published_on", "closure_notified_on", "decision_notified_on",
          "registered_on", "procedure_closed_on", "eu_grant_on", "expires_on")
URGENT_DAYS = 14
# A dead mark keeps no deadlines; a planned one has no events yet. An expired mark is not dead: it keeps the
# renewal grace period, the one date that decides whether the right is lost.
INACTIVE = {"refused", "withdrawn", "planned"}
GRACE = ".renewal-grace-ends"
CHECK_NOTE = "raw date, not verified on the task date; no shift to a working day applied"


class TrademarkInputError(ValueError):
    """Bad portfolio or rule input; the message says which file, mark and field."""


def add_months(day: dt.date, months: int) -> dt.date:
    """Same day number in the target month, else its last day.

    This is the EUIPO rule (Reg. 2018/625 art. 67(3)); the national offices are assumed to count the same way
    until their rule is read, which is why every result carries CHECK_NOTE.
    """
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return dt.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def parse_date(value: object, where: str) -> dt.date:
    if not isinstance(value, str):
        raise TrademarkInputError(f"{where}: expected a date YYYY-MM-DD, got {value!r}")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise TrademarkInputError(f"{where}: not a date YYYY-MM-DD: {value!r}") from exc


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TrademarkInputError(f"{path}: file not found") from exc
    except json.JSONDecodeError as exc:
        raise TrademarkInputError(f"{path}: not valid JSON (line {exc.lineno})") from exc
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise TrademarkInputError(f"{path}: expected an object with schema_version {SCHEMA_VERSION}")
    return data


def load_rules(path: Path = RULES_FILE) -> list[dict]:
    rules = load_json(path).get("rules")
    if not isinstance(rules, list) or not rules:
        raise TrademarkInputError(f"{path}: 'rules' must be a non-empty list")
    for rule in rules:
        rid = rule.get("id", "?")
        if rule.get("event") not in EVENTS:
            raise TrademarkInputError(f"{path}: rule {rid}: unknown event {rule.get('event')!r}")
        if rule.get("office") != "*" and rule.get("office") not in OFFICES:
            raise TrademarkInputError(f"{path}: rule {rid}: unknown office {rule.get('office')!r}")
        if ("months" in rule) == ("days" in rule):
            raise TrademarkInputError(f"{path}: rule {rid}: give exactly one of 'months' or 'days'")
    return rules


def apply_rule(rule: dict, event_day: dt.date) -> dt.date:
    if "months" in rule:
        return add_months(event_day, int(rule["months"]))
    return event_day + dt.timedelta(days=int(rule["days"]))


def validate_mark(mark: object, index: int, path: Path) -> dict:
    if not isinstance(mark, dict):
        raise TrademarkInputError(f"{path}: marks[{index}] must be an object")
    where = f"{path}: mark {mark.get('id') or index}"
    if not mark.get("id") or not mark.get("name"):
        raise TrademarkInputError(f"{where}: 'id' and 'name' are required")
    if mark.get("office") not in OFFICES:
        raise TrademarkInputError(f"{where}: office must be one of {sorted(OFFICES)}, got {mark.get('office')!r}")
    if mark.get("status") not in STATUSES:
        raise TrademarkInputError(f"{where}: status must be one of {sorted(STATUSES)}, got {mark.get('status')!r}")
    for event in EVENTS:
        if mark.get(event) is not None:
            parse_date(mark[event], f"{where}: {event}")
    return mark


def load_portfolio(path: Path) -> list[dict]:
    marks = load_json(path).get("marks")
    if not isinstance(marks, list):
        raise TrademarkInputError(f"{path}: 'marks' must be a list")
    seen: set[str] = set()
    out = []
    for i, mark in enumerate(marks):
        mark = validate_mark(mark, i, path)
        if mark["id"] in seen:
            raise TrademarkInputError(f"{path}: mark id {mark['id']!r} appears twice")
        seen.add(mark["id"])
        out.append(mark)
    return out


def mark_deadlines(mark: dict, rules: list[dict], today: dt.date) -> list[dict]:
    if mark["status"] in INACTIVE:
        return []
    events = {e: dt.date.fromisoformat(mark[e]) for e in EVENTS if mark.get(e)}
    applicable = [r for r in rules if r["office"] in ("*", mark["office"])]
    # Without the office's expiry date the renewal window still matters: start it from the computed 10-year term
    # and say so in the note, so a portfolio with only a filing date still shows its renewal dates.
    computed_expiry = False
    if "expires_on" not in events:
        term = next((r for r in applicable if r.get("replaced_by") == "expires_on" and r["event"] in events), None)
        if term is not None:
            events["expires_on"] = apply_rule(term, events[term["event"]])
            computed_expiry = True
    found = []
    for rule in applicable:
        if rule["event"] not in events:
            continue
        # A recorded expiry from the office beats our 10-year computation.
        if rule.get("replaced_by") in events and not computed_expiry:
            continue
        if mark["status"] == "expired" and not rule["id"].endswith(GRACE):
            continue
        end = apply_rule(rule, events[rule["event"]])
        days_left = (end - today).days
        note = CHECK_NOTE
        if computed_expiry and rule["event"] == "expires_on":
            note += "; counted from the computed term, not from an expiry date of the office"
        found.append({
            "mark": mark["id"], "name": mark["name"], "office": mark["office"], "rule": rule["id"],
            "what": rule["what"], "date": end.isoformat(), "days_left": days_left,
            "urgent": 0 <= days_left < URGENT_DAYS, "kind": rule["kind"], "basis": rule["basis"],
            "status": rule["status"], "note": note,
        })
    # The renewal grace period matters only once the term has ended.
    return [d for d in found if not (d["rule"].endswith(GRACE) and events.get("expires_on", today) > today)]


def portfolio_deadlines(path: Path, today: dt.date, horizon_days: int | None, include_past: bool,
                        rules: list[dict] | None = None) -> list[dict]:
    rules = rules if rules is not None else load_rules()
    rows = [d for m in load_portfolio(path) for d in mark_deadlines(m, rules, today)]
    if not include_past:
        rows = [d for d in rows if d["days_left"] >= 0]
    if horizon_days is not None:
        rows = [d for d in rows if d["days_left"] <= horizon_days]
    return sorted(rows, key=lambda d: (d["date"], d["mark"], d["rule"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("rules")
    c = sub.add_parser("compute")
    c.add_argument("--rule", required=True)
    c.add_argument("--date", required=True)
    p = sub.add_parser("portfolio")
    p.add_argument("--file", required=True, type=Path)
    p.add_argument("--today")
    p.add_argument("--horizon-days", type=int)
    p.add_argument("--all", action="store_true", help="include dates already past")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "rules":
            out: object = load_rules()
        elif args.cmd == "compute":
            rule = next((r for r in load_rules() if r["id"] == args.rule), None)
            if rule is None:
                raise TrademarkInputError(f"unknown rule {args.rule!r}; see the 'rules' command")
            end = apply_rule(rule, parse_date(args.date, "--date"))
            out = {"rule": rule["id"], "what": rule["what"], "date": end.isoformat(), "basis": rule["basis"],
                   "status": rule["status"], "note": CHECK_NOTE}
        else:
            today = parse_date(args.today, "--today") if args.today else dt.date.today()
            out = portfolio_deadlines(args.file, today, args.horizon_days, args.all)
    except TrademarkInputError as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # why: a Windows pipe defaults to the ANSI code page (no ș, ț, Cyrillic)
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8")
    sys.exit(main())
