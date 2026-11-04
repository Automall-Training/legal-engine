#!/usr/bin/env python3
"""Profile, modules and matters of the legal engine (stdlib only). Prints JSON for the agent.

    legal_profile.py where                                  # profile folder and where the path came from
    legal_profile.py status [--module M]                    # setup steps, missing steps, module states
    legal_profile.py module M                               # core | on | off | not-installed
    legal_profile.py matter new --slug S --title T --module M [--date YYYY-MM-DD]
    legal_profile.py matter log ID --event E [--note N] [--date YYYY-MM-DD]
    legal_profile.py matter list [--open]

The contract (folders, config.json, modules.json, integration-status.md) is in references/profile.md and
references/matters.md. Exit code 0 = done, 2 = a typed error with a message on stderr.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

# why: the unresolved path keeps the installed skills folder (install.sh links each skill), so sibling
# modules are looked up where the host actually loads them; the resolved one finds the engine repo.
SKILL_DIR = Path(os.path.abspath(__file__)).parent.parent
SIBLINGS = SKILL_DIR.parent
ENGINE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CATALOG = SKILL_DIR / "assets" / "modules.json"
CONFIG = Path(os.environ.get("LEGAL_ENGINE_CONFIG", Path.home() / ".config" / "legal-engine" / "config.json"))
DEFAULT_PROFILE = Path.home() / "legal-profile"

SCHEMA_VERSION = 1
STEP_STATES = ("done", "skipped", "pending")
SATISFIED = ("done", "skipped")
# why: a step marked done whose file is gone is not done; the router must not trust the table blindly.
STEP_FILES = {
    "firms": "context/company.md",
    "modules": "modules.json",
    "language": "context/language.md",
    "side-risk": "context/side-and-risk.md",
    "laws": "laws/watchlist.yaml",
}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EVENTS = ("opened", "waiting", "resumed", "done", "dropped", "note")
OPEN_STATES = ("opened", "waiting", "resumed")
LOG_HEADER = (
    "# Matters log\n\n"
    "Append-only: one row per event, newest last. The last non-note row of a matter is its status.\n\n"
    "| Date | Matter | Module | Event | Note |\n"
    "|---|---|---|---|---|\n"
)
LOG_ROW = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|\s]+)\s*\|\s*([^|\s]+)\s*\|\s*([a-z]+)\s*\|(.*)\|\s*$")


class LegalProfileError(Exception):
    """Base of every error this script reports to the agent."""


class ConfigError(LegalProfileError):
    """config.json is unreadable or has no usable profile_dir."""


class ProfileLocationError(LegalProfileError):
    """The profile would sit inside the public engine folder."""


class CatalogError(LegalProfileError):
    """The engine's module catalog is broken (a bug of the engine, not of the user)."""


class ModulesFileError(LegalProfileError):
    """The profile's modules.json does not match the contract."""


class StatusFileError(LegalProfileError):
    """The profile's context/integration-status.md has an unknown step state."""


class MatterError(LegalProfileError):
    """A matter cannot be created, logged or read."""


# ---------- profile ----------

def resolve_profile(config: Path = CONFIG) -> tuple[Path, str]:
    """(profile folder, where the path came from). A broken config is reported, never guessed around."""
    if not config.is_file():
        path, source = DEFAULT_PROFILE, "default (no config yet)"
    else:
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"config {config} is not valid JSON: {exc}") from exc
        raw = data.get("profile_dir") if isinstance(data, dict) else None
        if not isinstance(raw, str) or not raw.strip():
            raise ConfigError(f"config {config} has no string field profile_dir")
        path = Path(os.path.expanduser(raw.strip()))
        if not path.is_absolute():
            raise ConfigError(f"config {config}: profile_dir must be an absolute path or start with ~, got {raw!r}")
        source = f"config {config}"
    engine = ENGINE_ROOT.resolve()
    if path.resolve() == engine or engine in path.resolve().parents:
        raise ProfileLocationError(
            f"profile {path} is inside the engine folder {engine}; a profile holds private data and must live "
            "outside it (default ~/legal-profile)")
    return path, source


def load_catalog(path: Path = CATALOG) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"module catalog {path} unreadable: {exc}") from exc
    steps = data.get("steps")
    mods = data.get("modules")
    if not isinstance(steps, list) or not isinstance(mods, dict) or not mods:
        raise CatalogError(f"module catalog {path}: needs a list 'steps' and a dict 'modules'")
    for need in data.get("base_needs", []):
        if need not in steps:
            raise CatalogError(f"module catalog: base need {need!r} is not a setup step")
    for mid, m in mods.items():
        if not isinstance(m, dict) or not isinstance(m.get("skill"), str) or not isinstance(m.get("core"), bool):
            raise CatalogError(f"module catalog: module {mid!r} needs 'skill' (str) and 'core' (bool)")
        for need in m.get("needs", []):
            if need not in steps:
                raise CatalogError(f"module catalog: module {mid!r} needs unknown step {need!r}")
    return data


def optional_ids(catalog: dict) -> list[str]:
    return [mid for mid, m in catalog["modules"].items() if not m["core"]]


def read_modules(profile: Path, catalog: dict) -> dict[str, bool] | None:
    """Switches of optional modules, or None when the wizard has not written modules.json yet."""
    path = profile / "modules.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ModulesFileError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise ModulesFileError(f"{path}: expected an object with \"schema_version\": {SCHEMA_VERSION}")
    allowed = optional_ids(catalog)
    out = {}
    for key, value in data.items():
        if key == "schema_version":
            continue
        if key not in allowed:
            raise ModulesFileError(f"{path}: unknown module {key!r}; optional modules are {', '.join(allowed)}")
        if not isinstance(value, bool):
            raise ModulesFileError(f"{path}: {key} must be true or false, got {value!r}")
        out[key] = value
    # why: a module the wizard did not ask about yet stays off until the user turns it on.
    return {mid: out.get(mid, False) for mid in allowed}


def read_steps(profile: Path, catalog: dict) -> dict[str, str]:
    """State of every setup step from the table in context/integration-status.md (missing row = pending)."""
    steps = {s: "pending" for s in catalog["steps"]}
    path = profile / "context" / "integration-status.md"
    if path.is_file():
        for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            cells = [c.strip() for c in raw.strip().strip("|").split("|")]
            if len(cells) < 2 or cells[0] not in steps:
                continue
            state = cells[1].lower()
            if state not in STEP_STATES:
                raise StatusFileError(f"{path}:{n}: step {cells[0]} has state {cells[1]!r}; "
                                      f"allowed: {', '.join(STEP_STATES)}")
            steps[cells[0]] = state
    for step, rel in STEP_FILES.items():
        if steps.get(step) == "done" and not (profile / rel).is_file():
            steps[step] = "pending"
    return steps


def module_state(mid: str, catalog: dict, switches: dict[str, bool] | None, siblings: Path = SIBLINGS) -> str:
    mods = catalog["modules"]
    if mid not in mods:
        raise LegalProfileError(f"unknown module {mid!r}; known: {', '.join(mods)}")
    if not (siblings / mods[mid]["skill"] / "SKILL.md").is_file():
        return "not-installed"
    if mods[mid]["core"]:
        return "core"
    return "on" if switches and switches.get(mid) else "off"


def status(profile: Path, source: str, catalog: dict, module: str | None = None,
           siblings: Path = SIBLINGS) -> dict:
    exists = profile.is_dir()
    steps = read_steps(profile, catalog) if exists else {s: "pending" for s in catalog["steps"]}
    switches = read_modules(profile, catalog) if exists else None
    needs = list(catalog.get("base_needs", []))
    if module is not None:
        state = module_state(module, catalog, switches, siblings)  # also validates the id
        needs += [n for n in catalog["modules"][module].get("needs", []) if n not in needs]
    missing = [s for s in needs if steps[s] not in SATISFIED]
    out = {
        "profile": str(profile),
        "source": source,
        "exists": exists,
        "steps": steps,
        "missing_steps": missing,
        "ready": exists and not missing,
        "modules": {mid: module_state(mid, catalog, switches, siblings) for mid in catalog["modules"]},
    }
    if module is not None:
        out["module"] = module
        out["module_state"] = state
    return out


# ---------- matters ----------

def _oneline(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _cell(text: str) -> str:
    # why: a pipe or a line break inside a note would break the markdown table row.
    return _oneline(text).replace("|", "\\|")


def _date(value: str | None) -> str:
    if value is None:
        return dt.date.today().isoformat()
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise MatterError(f"date must be YYYY-MM-DD, got {value!r}") from exc


def _matters_dir(profile: Path) -> Path:
    if not profile.is_dir():
        raise MatterError(f"profile {profile} does not exist; run the setup wizard first")
    return profile / "matters"


def _append_log(matters: Path, date: str, matter_id: str, module: str, event: str, note: str) -> None:
    log = matters / "log.md"
    if not log.is_file():
        log.write_text(LOG_HEADER, encoding="utf-8")
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"| {date} | {matter_id} | {module} | {event} | {_cell(note)} |\n")


def matter_new(profile: Path, slug: str, title: str, module: str, catalog: dict, date: str | None = None) -> dict:
    if not SLUG.match(slug) or len(slug) > 60:
        raise MatterError(f"slug must be lowercase latin words joined by '-', up to 60 chars, got {slug!r}")
    if module not in catalog["modules"]:
        raise MatterError(f"unknown module {module!r}; known: {', '.join(catalog['modules'])}")
    title = _oneline(title)
    if not title or len(title) > 200:
        raise MatterError("title must be 1–200 characters")
    day = _date(date)
    matters = _matters_dir(profile)
    matters.mkdir(exist_ok=True)
    base = f"{day}-{slug}"
    for n in range(1, 100):
        matter_id = base if n == 1 else f"{base}-{n:02d}"
        folder = matters / matter_id
        try:
            folder.mkdir()  # why: mkdir without exist_ok is the atomic claim of the name
            break
        except FileExistsError:
            continue
    else:
        raise MatterError(f"99 matters named {base} already exist; choose another slug")
    intake = {
        "schema_version": SCHEMA_VERSION, "task_id": matter_id, "module": module, "title": title,
        "created": day, "action": None, "document_type": None, "commercial_goal": None,
        "represented_party": None, "parties": [], "confirmed_facts": [], "assumptions": [], "unknowns": [],
        "governing_law": None, "forum": None, "cross_border_factors": [], "execution_date": None,
        "performance_period": None, "analysis_date": None, "checked_at": None, "agreed_constraints": [],
        "communication_language": None, "document_language": None, "language_reason": None, "input_files": [],
    }
    (folder / "intake.json").write_text(json.dumps(intake, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _append_log(matters, day, matter_id, module, "opened", title)
    return {"id": matter_id, "path": str(folder), "module": module}


def _read_intake(folder: Path) -> dict:
    try:
        return json.loads((folder / "intake.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MatterError(f"{folder.name}: intake.json unreadable: {exc}") from exc


def matter_log(profile: Path, matter_id: str, event: str, note: str = "", date: str | None = None) -> dict:
    if event not in EVENTS:
        raise MatterError(f"event must be one of {', '.join(EVENTS)}, got {event!r}")
    matters = _matters_dir(profile)
    if not SLUG.match(matter_id) or not (matters / matter_id).is_dir():
        raise MatterError(f"no matter {matter_id!r} in {matters}")
    module = _read_intake(matters / matter_id).get("module") or "unknown"
    day = _date(date)
    _append_log(matters, day, matter_id, module, event, note)
    return {"id": matter_id, "event": event, "date": day}


def matter_list(profile: Path, only_open: bool = False) -> list[dict]:
    log = _matters_dir(profile) / "log.md"
    if not log.is_file():
        return []
    seen: dict[str, dict] = {}
    for raw in log.read_text(encoding="utf-8").splitlines():
        m = LOG_ROW.match(raw)
        if not m or m.group(4) not in EVENTS:
            continue
        date, mid, module, event, note = m.groups()
        item = seen.setdefault(mid, {"id": mid, "module": module, "status": None, "updated": date, "title": ""})
        item["updated"] = date
        if event == "opened":
            item["title"] = note.strip().replace("\\|", "|")
        if event != "note":
            item["status"] = event
    items = list(seen.values())
    return [i for i in items if i["status"] in OPEN_STATES] if only_open else items


# ---------- CLI ----------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("where")
    st = sub.add_parser("status")
    st.add_argument("--module")
    mo = sub.add_parser("module")
    mo.add_argument("module")
    ma = sub.add_parser("matter")
    msub = ma.add_subparsers(dest="action", required=True)
    mn = msub.add_parser("new")
    mn.add_argument("--slug", required=True)
    mn.add_argument("--title", required=True)
    mn.add_argument("--module", required=True)
    mn.add_argument("--date")
    ml = msub.add_parser("log")
    ml.add_argument("id")
    ml.add_argument("--event", required=True)
    ml.add_argument("--note", default="")
    ml.add_argument("--date")
    mls = msub.add_parser("list")
    mls.add_argument("--open", action="store_true")
    a = ap.parse_args(argv)
    try:
        # why: globals are read at call time so tests (and LEGAL_ENGINE_CONFIG) can point elsewhere.
        profile, source = resolve_profile(CONFIG)
        if a.cmd == "where":
            out: object = {"profile": str(profile), "source": source, "exists": profile.is_dir()}
        else:
            catalog = load_catalog()
            if a.cmd == "status":
                out = status(profile, source, catalog, a.module, SIBLINGS)
            elif a.cmd == "module":
                switches = read_modules(profile, catalog) if profile.is_dir() else None
                out = {"module": a.module, "state": module_state(a.module, catalog, switches, SIBLINGS),
                       "skill": catalog["modules"][a.module]["skill"]}
            elif a.action == "new":
                out = matter_new(profile, a.slug, a.title, a.module, catalog, a.date)
            elif a.action == "log":
                out = matter_log(profile, a.id, a.event, a.note, a.date)
            else:
                out = matter_list(profile, a.open)
    except LegalProfileError as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
