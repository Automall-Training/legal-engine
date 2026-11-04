#!/usr/bin/env python3
"""Check a version card (the current-version check of one act) for completeness and consistency (stdlib only).

    python3 check_version.py <matter>/work/versions/<act>.json [--root <matter>]

Prints JSON. Exit 0 = structure passed, 1 = structural errors (listed), 2 = the card cannot be read.
It never visits a site and never proves the law: it checks that every claim the card makes is recorded the way
references/version-check.md requires, and, where a saved official text is given, that each quote is really in it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

# why: the seven questions of a current-version check; each needs evidence or an honest "not verified".
POINTS = ("consolidation", "amendments", "deferred_entry", "secondary_acts", "case_law", "repeal",
          "status_of_changes")
# why: with scope "text" related acts and case law may stay open without blocking "current"; they are still gaps.
REQUIRED = {"full": set(POINTS), "text": set(POINTS) - {"secondary_acts", "case_law"}}
POINT_STATUSES = {"done", "not_verified"}
RESULTS = {"current", "outdated", "not_verified"}
CHANGE_STATUSES = {"in_force", "published_not_in_force", "draft"}
RELATED_KINDS = {"government_decision", "order", "authority_decision", "constitutional_court", "supreme_court",
                 "cjeu", "guidance"}
RELATED_EFFECTS = {"amends", "details", "suspends", "declares_unconstitutional", "interprets"}
MAX_QUOTE = 300
# why: an archived copy proves the text on the copy date only; older than this it cannot confirm currency.
ARCHIVE_MAX_DAYS = 14


class CardError(ValueError):
    """The version card cannot be read as a JSON object."""


def moment(value: str) -> datetime:
    """An ISO timestamp with a timezone, as in the source register."""
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError(f"timestamp without timezone: {value}")
    return stamp


def normalise(text: str) -> str:
    """Compare quotes loosely enough for layout, strictly enough for words.

    why: official HTML and PDF differ in spaces, line breaks, typographic quotes and the old Romanian cedilla
    letters (ş ţ vs ș ț); none of that changes the rule, every other character does.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.translate(str.maketrans({"ş": "ș", "Ş": "Ș", "ţ": "ț", "Ţ": "Ț", "„": '"', "”": '"', "“": '"',
                                         "«": '"', "»": '"', "’": "'", "‘": "'", " ": " ", "–": "-",
                                         "—": "-"}))
    return re.sub(r"\s+", " ", text).strip()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def validate(card: dict, now: datetime, root: Path | None = None) -> dict:
    errors: list[str] = []
    gaps: list[str] = []
    quotes = {"checked": 0, "unchecked": 0}

    def require(ok: bool, msg: str) -> None:
        if not ok:
            errors.append(msg)

    def evidence_ok(label: str, ev: dict, checked: datetime) -> bool:
        """Validate one piece of evidence; return True when it can confirm currency today."""
        require(str(ev.get("url", "")).startswith(("https://", "http://")), label + "evidence without a URL")
        opened = moment(ev["opened_at"])
        require(opened <= checked, label + "evidence opened after checked_at")
        quote = ev.get("quote") or ""
        require(bool(quote.strip()), label + "evidence without a verbatim quote")
        require(len(quote) <= MAX_QUOTE, label + f"quote longer than {MAX_QUOTE} characters")
        archived = ev.get("archived_on")
        require(ev.get("official") is True or bool(archived),
                label + "evidence neither official nor an archived official copy")
        if ev.get("text_file"):
            check_quote(label, ev, quote)
        else:
            quotes["unchecked"] += 1
        if archived:
            age = (checked.date() - date.fromisoformat(archived)).days
            if age > ARCHIVE_MAX_DAYS:
                gaps.append(label + f"archived copy is {age} days old: it confirms the text, not the current version")
                return False
        return True

    def check_quote(label: str, ev: dict, quote: str) -> None:
        if root is None:
            errors.append(label + "text_file given: pass --root <matter>")
            return
        path = root / ev["text_file"]
        if not _inside(path, root):
            errors.append(label + "text_file outside the matter folder")
            return
        try:
            data = path.read_bytes()
        except OSError as exc:
            errors.append(label + f"saved text cannot be read: {exc.strerror or exc}")
            return
        if ev.get("text_sha256"):
            require(hashlib.sha256(data).hexdigest() == ev["text_sha256"], label + "saved text changed (sha256)")
        text = data.decode("utf-8", errors="replace")
        found = normalise(quote) in normalise(text)
        require(found, label + "quote not found in the saved text")
        quotes["checked"] += 1

    try:
        require(card.get("schema_version", 1) == 1, "unsupported schema_version")
        act = card["act"]
        require(bool(act.get("id")) and bool(act.get("title")), "act needs id and title")
        checked = moment(card["checked_at"])
        analysis = date.fromisoformat(card["analysis_date"])
        require(checked <= now, "checked_at is in the future")
        require(checked.astimezone(now.tzinfo).date() == now.date(), "card is not from today: re-check required")
        scope = card.get("scope", "full")
        require(scope in REQUIRED, "scope must be 'full' or 'text'")
        required = REQUIRED.get(scope, REQUIRED["full"])
        require(bool(card.get("cited_provisions")), "no cited provisions: say which articles the answer relies on")

        open_required: list[str] = []
        stale: list[str] = []
        points = card["points"]
        for name in POINTS:
            label = name + ": "
            point = points.get(name)
            if not isinstance(point, dict):
                errors.append(label + "missing (record it, or mark it not_verified with a reason)")
                open_required.append(name)
                continue
            status = point.get("status")
            require(status in POINT_STATUSES, label + "status must be done or not_verified")
            if status == "done":
                evidence = point.get("evidence") or []
                # why: "no amendments" is a claim too; it needs the page that shows the list and its last entry.
                require(bool(evidence), label + "done without evidence")
                require(bool(point.get("note")), label + "done without a note of what was found")
                fresh = [evidence_ok(f"{label}evidence {i + 1}: ", ev, checked) for i, ev in enumerate(evidence)]
                if evidence and not any(fresh):
                    stale.append(name)
            else:
                require(bool(point.get("reason")), label + "not_verified needs a reason")
                require(bool(point.get("depends")), label + "not_verified needs what depends on it")
                gaps.append(label + str(point.get("reason", "")) + " → " + str(point.get("depends", "")))
                if name in required:
                    open_required.append(name)

        latest = card.get("latest_in_force") or {}
        latest_from = date.fromisoformat(latest["version_from"]) if latest.get("version_from") else None
        if latest_from:
            # why: registers list the newest version first even when it applies only later; that one is "next".
            require(latest_from <= analysis, "latest_in_force applies after the analysis date: it is a next version")
        for i, nxt in enumerate(card.get("next_versions", [])):
            require(date.fromisoformat(nxt["applies_from"]) > analysis,
                    f"next version {i + 1} already applies on the analysis date: it is in force, not next")

        held = card.get("held_version") or {}
        held_from = date.fromisoformat(held["version_from"]) if held.get("version_from") else None
        newer_change = False
        for i, ch in enumerate(card.get("changes", [])):
            label = f"change {i + 1}: "
            require(ch.get("status") in CHANGE_STATUSES, label + "unknown status")
            require(bool(ch.get("act")) and bool(ch.get("published")), label + "needs the amending act and publication")
            if ch.get("status") == "draft":
                # why: a bill or a proposal is not law; it may be mentioned for information only.
                require(not ch.get("affects_conclusion"), label + "a draft cannot change the conclusion")
            if ch.get("status") == "published_not_in_force" and ch.get("applies_from"):
                require(date.fromisoformat(ch["applies_from"]) > analysis,
                        label + "'published_not_in_force' but applies on the analysis date")
            if ch.get("status") == "in_force" and ch.get("applies_from") and held_from:
                applies = date.fromisoformat(ch["applies_from"])
                newer_change = newer_change or held_from < applies <= analysis

        for i, rel in enumerate(card.get("related", [])):
            label = f"related {i + 1}: "
            require(rel.get("kind") in RELATED_KINDS, label + "unknown kind")
            require(rel.get("effect") in RELATED_EFFECTS, label + "unknown effect")
            require(isinstance(rel.get("binding"), bool), label + "say whether it binds (true/false)")
            if rel.get("kind") == "guidance":
                require(rel.get("binding") is False, label + "guidance is not law: binding must be false")
            require(str(rel.get("url", "")).startswith(("https://", "http://")), label + "needs a URL")

        result = card.get("result")
        require(result in RESULTS, "result must be current, outdated or not_verified")
        behind = bool(held_from and latest_from and held_from < latest_from)
        if result == "current":
            require(not open_required, "current needs every required point done: " + ", ".join(open_required))
            require(not [p for p in stale if p in required],
                    "current cannot rest on old archived copies only: " + ", ".join(p for p in stale if p in required))
            require(latest_from is not None, "current needs latest_in_force.version_from")
            require(not behind, "the held version is older than the latest in force: result is outdated")
            require(not newer_change, "a change in force after the held version: result is outdated")
        if result == "outdated":
            require(bool(card.get("outdated_reason")), "outdated needs outdated_reason")
        if result == "not_verified":
            require(bool(open_required or stale), "not_verified but every required point is closed")
            require(bool(card.get("working_conclusion")),
                    "not_verified needs a working_conclusion (last known text, its date, what stays open)")
        if result != "outdated" and (behind or newer_change):
            errors.append("the held version is behind the law in force: result must be outdated")
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        errors.append(f"invalid schema/date: {exc!r}")
    return {"structural_status": "failed" if errors else "passed", "result": card.get("result"),
            "errors": errors, "gaps": gaps, "quotes": quotes, "legal_truth_checked": False}


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CardError(f"cannot read the version card {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CardError(f"the version card {path} must be a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("card", type=Path)
    ap.add_argument("--root", type=Path, help="matter folder; saved texts (text_file) are relative to it")
    args = ap.parse_args(argv)
    try:
        result = validate(load(args.card), datetime.now().astimezone(), args.root)
    except CardError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
