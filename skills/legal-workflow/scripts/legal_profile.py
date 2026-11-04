#!/usr/bin/env python3
"""Profile, modules and matters of the legal engine (stdlib only). Prints JSON for the agent.

    legal_profile.py where                                  # profile folder and where the path came from
    legal_profile.py status [--module M]                    # setup steps, missing steps, module states
    legal_profile.py module M                               # core | on | off | unset | not-installed
    legal_profile.py step set STEP --status S [--note N] [--date YYYY-MM-DD]   # the wizard records a step
    legal_profile.py matter new --slug S --title T --module M [--date YYYY-MM-DD]
    legal_profile.py matter log ID --event E [--note N] [--date YYYY-MM-DD]
    legal_profile.py matter update ID --data JSON|@file     # a module fills intake.json (core fields, module_data)
    legal_profile.py matter show ID
    legal_profile.py matter list [--open]

The contract (folders, config.json, modules.json, integration-status.md, matters) is in
references/profile.md and references/matters.md. Exit code 0 = done, 2 = a typed error on stderr.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
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
STATUS_FILE = Path("context") / "integration-status.md"
STATUS_HEADER = "| Step | Status | Updated | Note |\n|---|---|---|---|\n"
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# why: "opened" is written only by `matter new`; a second one would silently retitle the matter.
EVENTS = ("waiting", "resumed", "done", "dropped", "note")
OPEN_STATES = ("opened", "waiting", "resumed")
LOG_HEADER = (
    "# Matters log\n\n"
    "Append-only: one row per event, newest last. The last non-note row of a matter is its status.\n\n"
    "| Date | Matter | Module | Event | Note |\n"
    "|---|---|---|---|---|\n"
)
LOG_ROW = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|\s]+)\s*\|\s*([^|\s]+)\s*\|\s*([a-z]+)\s*\|(.*)\|\s*$")
READ_ERRORS = (OSError, UnicodeDecodeError, json.JSONDecodeError)


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
    """The profile's context/integration-status.md cannot be read or has an unknown step state."""


class MatterError(LegalProfileError):
    """A matter cannot be created, logged or read."""


def _read_json(path: Path, error: type[LegalProfileError]) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except READ_ERRORS as exc:
        raise error(f"{path} unreadable or not valid UTF-8 JSON: {exc}") from exc


# ---------- profile ----------

def resolve_profile(config: Path = CONFIG) -> tuple[Path, str]:
    """(profile folder, where the path came from). A broken config is reported, never guessed around."""
    if not config.is_file():
        path, source = DEFAULT_PROFILE, "default (no config yet)"
    else:
        data = _read_json(config, ConfigError)
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
    data = _read_json(path, CatalogError)
    steps = data.get("steps") if isinstance(data, dict) else None
    mods = data.get("modules") if isinstance(data, dict) else None
    if not isinstance(steps, dict) or not steps or not isinstance(mods, dict) or not mods:
        raise CatalogError(f"module catalog {path}: needs a dict 'steps' (id → file or null) and a dict 'modules'")
    for step, rel in steps.items():
        if rel is not None and not isinstance(rel, str):
            raise CatalogError(f"module catalog: step {step!r} file must be a string or null")
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
    data = _read_json(path, ModulesFileError)
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise ModulesFileError(f"{path}: expected an object with \"schema_version\": {SCHEMA_VERSION} "
                               "(another version → run legal-workflow-update)")
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


def _status_lines(profile: Path) -> list[str]:
    path = profile / STATUS_FILE
    if not path.is_file():
        return []
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise StatusFileError(f"{path} unreadable: {exc}") from exc


def _row_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def read_steps(profile: Path, catalog: dict) -> dict[str, str]:
    """State of every setup step from the table in context/integration-status.md (missing row = pending)."""
    steps = {s: "pending" for s in catalog["steps"]}
    for n, raw in enumerate(_status_lines(profile), 1):
        cells = _row_cells(raw)
        if len(cells) < 2 or cells[0] not in steps:
            continue
        state = cells[1].lower()
        if state not in STEP_STATES:
            raise StatusFileError(f"{profile / STATUS_FILE}:{n}: step {cells[0]} has state {cells[1]!r}; "
                                  f"allowed: {', '.join(STEP_STATES)}")
        steps[cells[0]] = state
    # why: a step marked done whose file is gone is not done; the router must not trust the table blindly.
    for step, rel in catalog["steps"].items():
        if rel and steps[step] == "done" and not (profile / rel).is_file():
            steps[step] = "pending"
    return steps


def step_set(profile: Path, step: str, state: str, catalog: dict, note: str = "", date: str | None = None) -> dict:
    """Write one step row (replace it if present). Only the wizard and the update skill call this."""
    if step not in catalog["steps"]:
        raise StatusFileError(f"unknown step {step!r}; steps: {', '.join(catalog['steps'])}")
    state = state.lower()  # why: the reader accepts any case, so the writer does too
    if state not in STEP_STATES:
        raise StatusFileError(f"status must be one of {', '.join(STEP_STATES)}, got {state!r}")
    if not profile.is_dir():
        raise StatusFileError(f"profile {profile} does not exist; create it first (setup wizard)")
    rel = catalog["steps"][step]
    # why: the reader downgrades such a row to pending, so the wizard would loop without knowing why.
    if state == "done" and rel and not (profile / rel).is_file():
        raise StatusFileError(f"step {step} cannot be done: write {profile / rel} first")
    day = _date(date, StatusFileError)
    row = f"| {step} | {state} | {day} | {_cell(note)} |"
    lines = _status_lines(profile) or ["# Integration status", ""]
    for i, raw in enumerate(lines):
        if _row_cells(raw)[0] == step and raw.lstrip().startswith("|"):
            lines[i] = row
            break
    else:
        if not any(raw.lstrip().startswith("| Step |") for raw in lines):
            lines += STATUS_HEADER.rstrip("\n").split("\n")
        lines.append(row)
    path = profile / STATUS_FILE
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)  # why: atomic, a crash never leaves a half-written status table
    return {"step": step, "status": state, "date": day}


def module_state(mid: str, catalog: dict, switches: dict[str, bool] | None, siblings: Path = SIBLINGS) -> str:
    mods = catalog["modules"]
    if mid not in mods:
        raise LegalProfileError(f"unknown module {mid!r}; known: {', '.join(mods)}")
    if not (siblings / mods[mid]["skill"] / "SKILL.md").is_file():
        return "not-installed"
    if mods[mid]["core"]:
        return "core"
    if switches is None:
        return "unset"  # why: no modules.json yet = the wizard has not asked, which is not the user saying "off"
    return "on" if switches.get(mid) else "off"


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


def _date(value: str | None, error: type[LegalProfileError] = MatterError) -> str:
    if value is None:
        return dt.date.today().isoformat()
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise error(f"date must be YYYY-MM-DD, got {value!r}") from exc


def _matters_dir(profile: Path) -> Path:
    if not profile.is_dir():
        raise MatterError(f"profile {profile} does not exist; run the setup wizard first")
    return profile / "matters"


def _append_log(matters: Path, date: str, matter_id: str, module: str, event: str, note: str) -> None:
    log = matters / "log.md"
    try:
        with log.open("x", encoding="utf-8") as fh:  # why: exclusive create, two writers never both write a header
            fh.write(LOG_HEADER)
    except FileExistsError:
        pass
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
    # why: the generic core is owned here; each module keeps its own fields under module_data.
    intake = {
        "schema_version": SCHEMA_VERSION, "task_id": matter_id, "module": module, "title": title, "created": day,
        "represented_party": None, "communication_language": None, "document_language": None,
        "input_files": [], "unknowns": [], "module_data": {},
    }
    try:
        for sub in ("input", "output", "work"):
            (folder / sub).mkdir()
        (folder / "intake.json").write_text(json.dumps(intake, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    except OSError as exc:
        shutil.rmtree(folder, ignore_errors=True)  # why: no half-made matter without a log row
        raise MatterError(f"cannot create matter {matter_id}: {exc}") from exc
    _append_log(matters, day, matter_id, module, "opened", title)
    return {"id": matter_id, "path": str(folder), "module": module}


def _matter_folder(profile: Path, matter_id: str) -> Path:
    matters = _matters_dir(profile)
    if not SLUG.match(matter_id) or not (matters / matter_id).is_dir():
        raise MatterError(f"no matter {matter_id!r} in {matters}")
    return matters / matter_id


def _read_intake(folder: Path) -> dict:
    data = _read_json(folder / "intake.json", MatterError)
    if not isinstance(data, dict):
        raise MatterError(f"{folder.name}: intake.json must be an object")
    return data


def matter_log(profile: Path, matter_id: str, event: str, note: str = "", date: str | None = None) -> dict:
    if event not in EVENTS:
        raise MatterError(f"event must be one of {', '.join(EVENTS)}, got {event!r}")
    folder = _matter_folder(profile, matter_id)
    module = _read_intake(folder).get("module") or "unknown"
    day = _date(date)
    _append_log(folder.parent, day, matter_id, module, event, note)
    return {"id": matter_id, "event": event, "date": day}


# why: the core fields a module may fill in later; identity fields stay as `matter new` wrote them.
INTAKE_EDITABLE = ("represented_party", "communication_language", "document_language", "input_files", "unknowns")
INTAKE_FIXED = ("schema_version", "task_id", "module", "title", "created")


def matter_update(profile: Path, matter_id: str, data: object) -> dict:
    """Merge a module's answers into intake.json: editable core fields are replaced, module_data keys merged."""
    if not isinstance(data, dict) or not data:
        raise MatterError("update data must be a non-empty JSON object")
    fixed = sorted(set(data) & set(INTAKE_FIXED))
    if fixed:
        raise MatterError(f"fields set by 'matter new' cannot change: {', '.join(fixed)}")
    unknown = sorted(set(data) - set(INTAKE_EDITABLE) - {"module_data"})
    if unknown:
        raise MatterError(f"unknown intake fields: {', '.join(unknown)}; core: {', '.join(INTAKE_EDITABLE)}, "
                          f"module fields go under module_data")
    if "module_data" in data and (not isinstance(data["module_data"], dict) or not data["module_data"]):
        raise MatterError("module_data must be a non-empty JSON object")
    for key in ("input_files", "unknowns"):
        if key in data and not isinstance(data[key], list):
            raise MatterError(f"{key} must be a list")
    for key in ("represented_party", "communication_language", "document_language"):
        if key in data and not (data[key] is None or isinstance(data[key], str)):
            raise MatterError(f"{key} must be a string or null")
    folder = _matter_folder(profile, matter_id)
    intake = _read_intake(folder)
    if intake.get("schema_version") != SCHEMA_VERSION:
        raise MatterError(f"{folder / 'intake.json'}: schema_version {intake.get('schema_version')!r} is not "
                          f"{SCHEMA_VERSION}; migrate it with legal-workflow-update")
    for key in INTAKE_EDITABLE:
        if key in data:
            intake[key] = data[key]
    if "module_data" in data:
        current = intake.get("module_data") if isinstance(intake.get("module_data"), dict) else {}
        intake["module_data"] = {**current, **data["module_data"]}
    target = folder / "intake.json"
    # why: a unique temp name per writer, then an atomic replace: a crash never leaves a broken intake.json.
    # Two writers at once still end with one whole file (last wins); modules update a matter one at a time.
    fd, name = tempfile.mkstemp(dir=folder, prefix=".intake-", suffix=".tmp")
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(intake, ensure_ascii=False, indent=2) + "\n")
        tmp.replace(target)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise MatterError(f"cannot write {target}: {exc}") from exc
    return {"id": matter_id, "updated": sorted(data)}


def _update_data(raw: str) -> object:
    """`--data` is JSON text, or @path to a JSON file (long texts in any language without shell quoting)."""
    try:
        text = Path(raw[1:]).expanduser().read_text(encoding="utf-8") if raw.startswith("@") else raw
        return json.loads(text)
    except READ_ERRORS as exc:
        raise MatterError(f"--data is not readable JSON: {exc}") from exc


def _log_rows(profile: Path) -> list[tuple[str, str, str, str, str]]:
    log = _matters_dir(profile) / "log.md"
    if not log.is_file():
        return []
    try:
        text = log.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise MatterError(f"{log} unreadable: {exc}") from exc
    rows = []
    for raw in text.splitlines():
        m = LOG_ROW.match(raw)
        if m and (m.group(4) in EVENTS or m.group(4) == "opened"):
            date, mid, module, event, note = m.groups()
            rows.append((date, mid, module, event, note.strip().replace("\\|", "|")))
    return rows


def matter_list(profile: Path, only_open: bool = False) -> list[dict]:
    seen: dict[str, dict] = {}
    for date, mid, module, event, note in _log_rows(profile):
        item = seen.setdefault(mid, {"id": mid, "module": module, "status": None, "updated": date, "title": ""})
        item["updated"] = date
        if event == "opened" and not item["title"]:
            item["title"] = note
        if event != "note":
            item["status"] = event
    items = list(seen.values())
    return [i for i in items if i["status"] in OPEN_STATES] if only_open else items


def matter_show(profile: Path, matter_id: str) -> dict:
    """Intake and full event history of one matter, so modules never parse log.md themselves."""
    folder = _matter_folder(profile, matter_id)
    events = [{"date": d, "event": e, "note": n} for d, mid, _m, e, n in _log_rows(profile) if mid == matter_id]
    current = [e["event"] for e in events if e["event"] != "note"]
    return {"id": matter_id, "path": str(folder), "status": current[-1] if current else None,
            "intake": _read_intake(folder), "events": events}


# ---------- CLI ----------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("where")
    st = sub.add_parser("status")
    st.add_argument("--module")
    mo = sub.add_parser("module")
    mo.add_argument("module")
    sp = sub.add_parser("step")
    ssub = sp.add_subparsers(dest="action", required=True)
    ss = ssub.add_parser("set")
    ss.add_argument("step")
    ss.add_argument("--status", required=True)
    ss.add_argument("--note", default="")
    ss.add_argument("--date")
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
    mu = msub.add_parser("update")
    mu.add_argument("id")
    mu.add_argument("--data", required=True)
    msh = msub.add_parser("show")
    msh.add_argument("id")
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
            elif a.cmd == "step":
                out = step_set(profile, a.step, a.status, catalog, a.note, a.date)
            elif a.action == "new":
                out = matter_new(profile, a.slug, a.title, a.module, catalog, a.date)
            elif a.action == "log":
                out = matter_log(profile, a.id, a.event, a.note, a.date)
            elif a.action == "update":
                out = matter_update(profile, a.id, _update_data(a.data))
            elif a.action == "show":
                out = matter_show(profile, a.id)
            else:
                out = matter_list(profile, a.open)
    except LegalProfileError as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
