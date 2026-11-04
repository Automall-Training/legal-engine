#!/usr/bin/env python3
"""Check a matter's source register for completeness and consistency, never for legal truth (stdlib only).

    python3 check_register.py <matter>/source-register.json --task-id <matter-id>@<YYYY-MM-DD>

Prints JSON. Exit 0 = structure passed, 1 = structural errors (listed), 2 = the file cannot be read.
A green result only means every claimed check is recorded; the agent still reads every rule itself.
The format and the rules behind each check: ../references/law-check.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

# why: a rule is "verified" only after each of these was looked at in the official text on the check date.
CHECKS = ("full_text", "amendments", "repeal", "renumbering", "entry_into_force", "application_date", "transitional")
SOURCE_FIELDS = ("title", "number", "jurisdiction", "authority_type", "legal_force", "provision", "version",
                 "url", "applicability", "status", "related_findings")
SOURCE_STATUSES = {"verified", "partial", "unavailable", "superseded", "future"}
OPENED_STATUSES = {"verified", "future", "superseded"}
FINDING_KINDS = {"mandatory", "risk_recommendation", "editorial"}
BASIS_KINDS = {"law", "practice"}
FINDING_STATUSES = {"verified", "conditional", "unverified"}
COMPLETIONS = {"verified_scope", "partial"}


class RegisterError(ValueError):
    """The register file cannot be read as JSON."""


def moment(value: str) -> datetime:
    """An ISO timestamp with a timezone: a date alone cannot prove the check ran today in the user's zone."""
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError(f"timestamp without timezone: {value}")
    return stamp


def validate(reg: dict, task_id: str, now: datetime) -> dict:
    errors: list[str] = []
    gaps: list[str] = []

    def require(ok: bool, msg: str) -> None:
        if not ok:
            errors.append(msg)

    try:
        # why: registers written before the field existed are version 1; another version needs migration.
        require(reg.get("schema_version", 1) == 1, "unsupported schema_version: migrate with legal-workflow-update")
        require(reg["task_id"] == task_id, "task_id mismatch: a new check is required for this task")
        start, checked = moment(reg["started_at"]), moment(reg["checked_at"])
        analysis = date.fromisoformat(reg["analysis_date"])
        require(start <= checked <= now, "invalid task/check timestamps")
        require(checked.astimezone(now.tzinfo).date() == now.date(), "check is not from today: re-check required")
        # why: the id carries the check date (<matter-id>@<YYYY-MM-DD>); a past analysis date there is a mistake.
        _, sep, day = str(reg["task_id"]).rpartition("@")
        require(bool(sep) and day == checked.astimezone(now.tzinfo).date().isoformat(),
                "task_id must be <matter-id>@<check date> (the date of checked_at, not the analysis date)")
        sources = {s["id"]: s for s in reg["sources"]}
        require(len(sources) == len(reg["sources"]), "duplicate source ids")
        findings = {f["id"]: f for f in reg["findings"]}
        require(len(findings) == len(reg["findings"]), "duplicate finding ids")
        require(bool(findings), "no scope/findings recorded")

        for sid, s in sources.items():
            label = sid + ": "
            for key in SOURCE_FIELDS:
                require(bool(s.get(key)), label + "missing " + key)
            require(s["status"] in SOURCE_STATUSES, label + "unknown status")
            require(s["url"].startswith(("https://", "http://")), label + "invalid URL")
            for fid in s["related_findings"]:
                require(fid in findings, label + "unknown finding " + fid)
            if s["status"] in OPENED_STATUSES:
                opened = moment(s["opened_at"])
                require(start <= opened <= checked, label + "source not opened in this run")
                for key in CHECKS:
                    item = s.get("checks", {}).get(key, {})
                    require(item.get("done") is True and bool(item.get("note")), label + "unchecked " + key)
                require(s.get("official_text") is True, label + "full official text not confirmed")
                require(bool(s.get("version_from")) and bool(s.get("applies_from")), label + "missing temporal scope")
                begins = date.fromisoformat(s["applies_from"])
                version_from = date.fromisoformat(s["version_from"])
                if s["status"] == "future":
                    require(begins > analysis, label + "'future' already applies on the analysis date")
                if s["status"] == "verified":
                    require(begins <= analysis, label + "not applicable yet on the analysis date")
                    require(version_from <= analysis, label + "version not in effect on the analysis date")
                    if s.get("version_to"):
                        require(analysis <= date.fromisoformat(s["version_to"]), label + "expired version")
            else:
                require(bool(s.get("unverified_impact")), label + "missing limitation impact")
                gaps.append(label + s.get("unverified_impact", ""))

        for fid, f in findings.items():
            require(f["kind"] in FINDING_KINDS, fid + ": unknown kind")
            require(f["basis_kind"] in BASIS_KINDS, fid + ": unknown basis kind")
            if f["kind"] == "mandatory":
                require(f["basis_kind"] == "law", fid + ": a mandatory claim needs law")
            require(bool(f.get("conclusion")), fid + ": missing conclusion")
            require(f.get("status") in FINDING_STATUSES, fid + ": missing finding status")
            ids = f.get("source_ids", [])
            if f["basis_kind"] == "law":
                require(bool(ids), fid + ": legal claim has no source")
            for sid in ids:
                require(sid in sources, fid + ": unknown source " + sid)
                if sid in sources:
                    require(fid in sources[sid]["related_findings"], fid + ": missing reverse source link")
                    # why: a future rule may only support a notice about the future, never a current breach.
                    allowed = {"future"} if f.get("temporal_role") == "future_notice" else {"verified"}
                    if f["status"] == "verified":
                        require(sources[sid]["status"] in allowed, fid + ": unsupported verified claim")
            if f["status"] != "verified":
                require(bool(f.get("unverified_impact")), fid + ": missing unresolved impact")
                if f.get("material", True):
                    gaps.append(fid + ": " + f.get("unverified_impact", ""))

        if reg.get("completion") == "verified_scope":
            require(not gaps, "cannot mark verified_scope with unresolved gaps")
        require(reg.get("completion") in COMPLETIONS, "unknown completion status")
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        errors.append(f"invalid schema/date: {exc!r}")
    return {"structural_status": "failed" if errors else "passed", "errors": errors, "unresolved": gaps,
            "legal_truth_checked": False}


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegisterError(f"cannot read the source register {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RegisterError(f"the source register {path} must be a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("register", type=Path)
    ap.add_argument("--task-id", required=True)
    args = ap.parse_args(argv)
    try:
        result = validate(load(args.register), args.task_id, datetime.now().astimezone())
    except RegisterError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
