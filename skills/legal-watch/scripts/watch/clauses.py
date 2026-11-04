"""The index "contract clause → law" for the user's contracts in force, and the re-review flags.

    <profile>/contracts/<file>                  a contract in force (copied there by the wizard or the user)
    <profile>/contracts/index/<file-stem>.json  its index

A clause depends on an act either because it cites it (`cited`, found by `scan`) or because its subject is
governed by it although the text does not say so (`inferred`, added by the agent after reading the clause).
When a monitoring run confirms a change of an act, every dependent clause gets `needs_reverify` with the
change; the engine then proposes a matter "re-review contract X" (audit and Word redline through
`legal-contracts`). A flag is cleared only after that re-review (`clear`); the engine never edits a contract.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import library as lib

SCHEMA = 1
SOURCES = ("cited", "inferred")
CONTRACT_SUFFIXES = (".docx", ".txt", ".md")

# Citations recognised in Romanian-language contract text (Moldova and Romania).
_KINDS = (r"Legea|Legii|OUG|O\.U\.G\.|Ordonan[țţt]a\s+de\s+urgen[țţt][ăa]|HG|H\.G\.|Hot[ăa]r[âa]rea\s+Guvernului|"
          r"Hot[ăa]r[âa]rii\s+Guvernului|OG|O\.G\.")
# Romanian style: "Legea nr. 287/2009".
LAW_RE = re.compile(rf"\b(?P<k>{_KINDS})\s*(?:nr\.?\s*)?(?P<n>\d+)(?:\s*-\s*[IVXL]+)?\s*/\s*(?P<y>\d{{4}})", re.I)
# Moldovan style: "Legea nr. 133 din 08.07.2011", "nr. 1125-XV din 13.06.2002", "din 8 iulie 2011".
LAW_DIN_RE = re.compile(rf"\b(?P<k>{_KINDS})\s*nr\.?\s*(?P<n>\d+)(?:\s*-\s*[IVXL]+)?\s+din\s+"
                        r"(?:\d{1,2}[./]\d{1,2}[./]|\d{1,2}\s+[a-zăâîșşțţ]+\s+)(?P<y>\d{4})", re.I)
# EU acts keep the order of the official citation: Regulation 2016/679 → eu.reg.2016-679, 593/2008 → 593-2008.
EU_RE = re.compile(r"\b(?P<k>Regulamentul(?:ui)?|Directiva|Directivei|Regulation|Directive)\s*"
                   r"(?:\((?:UE|EU|CE|EC|CEE|EEC)\)\s*)?(?:nr\.?\s*)?(?P<a>\d{2,4})/(?P<b>\d{2,4})", re.I)
CODE_RE = re.compile(r"\bCod(?:ul|ului)\s+(?P<c>civil|muncii|fiscal|penal|educa[țţt]iei|audiovizual|"
                     r"de\s+procedur[ăa]\s+(?:civil|fiscal)[ăa]|contraven[țţt]ional|administrativ|vamal)\b", re.I)
ARTICLE_RE = re.compile(r"\bart(?:icolul|\.)\s*(?P<a>\d+(?:\^?\d+)?)(?:\s*(?:alin\.|al\.)\s*\((?P<p>\d+)\))?", re.I)
# A clause number: "5.2", "5.2.", "5.", "Art. 5" at the start of a line; "30 de zile" is not a clause.
CLAUSE_RE = re.compile(r"^\s*(?:Art(?:icolul|\.)\s*(?P<a>\d{1,3})\b|(?P<c>\d{1,2}(?:\.\d{1,2}){1,3})\.?\s+\S|"
                       r"(?P<d>\d{1,2})[.)]\s+\S)")
KIND = {"legea": "lege", "legii": "lege", "oug": "oug", "o.u.g.": "oug", "hg": "hg", "h.g.": "hg", "og": "og",
        "o.g.": "og"}
_FOLD = str.maketrans("ăâîșşțţ", "aaisstt")


def code_slug(name: str) -> str:
    """'de procedură civilă' → 'procedura-civila' (the `code` field of the catalog)."""
    words = name.lower().translate(_FOLD).split()
    return "-".join(w for w in words if w != "de")


def catalog_codes(acts: dict[str, dict]) -> dict[tuple[str, str], str]:
    """(jurisdiction, code) → catalog id: Romanian codes live under their approving law (ro.lege.287-2009)."""
    return {(a["jurisdiction"], a["code"]): i for i, a in acts.items() if a.get("code")}


def index_dir(profile: Path) -> Path:
    return Path(profile) / "contracts" / "index"


def contract_text(path: Path) -> list[str]:
    """Paragraphs of a contract (DOCX through python-docx, otherwise plain text)."""
    path = Path(path)
    if path.suffix.lower() == ".docx":
        try:
            import docx
        except ImportError as e:
            raise lib.WatchError("python-docx is missing: run with the engine's .venv/bin/python") from e
        doc = docx.Document(str(path))
        # Contracts often keep clauses in tables (annexes, price lists): read their cells too.
        cells = [c.text for t in doc.tables for row in t.rows for c in row.cells]
        return [p.text for p in doc.paragraphs] + cells
    if path.suffix.lower() in (".txt", ".md"):
        return path.read_text(encoding="utf-8").splitlines()
    raise lib.WatchError(f"unsupported contract format {path.suffix!r}; use {', '.join(CONTRACT_SUFFIXES)}")


def _law_kind(raw: str) -> str:
    low = re.sub(r"\s+", "", raw.lower())
    if low.startswith("ordonan"):
        return "oug" if "urgen" in low else "og"
    if low.startswith("hot"):
        return "hg"
    return KIND.get(low, "lege")


def citations(line: str, jurisdiction: str, codes: dict[tuple[str, str], str] | None = None
              ) -> list[tuple[str, str | None]]:
    """(act id, provision) pairs cited in one line; the jurisdiction decides the prefix of national acts."""
    pre = jurisdiction.lower()
    arts = [m.group("a") + (f" alin. ({m.group('p')})" if m.group("p") else "") for m in ARTICLE_RE.finditer(line)]
    prov = f"art. {arts[0]}" if len(arts) == 1 else None
    found: list[tuple[str, str | None]] = []
    for m in [*LAW_RE.finditer(line), *LAW_DIN_RE.finditer(line)]:
        kind = _law_kind(m.group("k"))
        kind = "lege" if pre == "md" and kind != "hg" else kind
        found.append((f"{pre}.{kind}.{m.group('n')}-{m.group('y')}", prov))
    for m in EU_RE.finditer(line):
        kind = "reg" if m.group("k").lower().startswith("reg") else "dir"
        found.append((f"eu.{kind}.{m.group('a')}-{m.group('b')}", prov))
    for m in CODE_RE.finditer(line):
        slug = code_slug(m.group("c"))
        found.append(((codes or {}).get((jurisdiction, slug)) or f"{pre}.cod.{slug}", prov))
    return list(dict.fromkeys(found))


def scan(path: Path, jurisdiction: str, codes: dict[tuple[str, str], str] | None = None) -> dict:
    """A draft index from the citations in the text; the agent completes it with `inferred` links."""
    if jurisdiction.upper() not in ("MD", "RO"):
        raise lib.WatchError("jurisdiction of the contract must be MD or RO (EU acts are found in both)")
    clause = None
    rows: dict[str, dict] = {}
    for line in contract_text(path):
        m = CLAUSE_RE.match(line)
        if m:
            clause = m.group("a") or m.group("c") or m.group("d")
        for act_id, prov in citations(line, jurisdiction.upper(), codes):
            key = clause or "-"
            row = rows.setdefault(key, {"clause": key, "topic": None, "acts": [], "source": "cited",
                                        "needs_reverify": False, "reverify": []})
            if not any(a["id"] == act_id and a.get("provision") == prov for a in row["acts"]):
                row["acts"].append({"id": act_id, "provision": prov})
    return {"schema_version": SCHEMA, "contract": Path(path).name, "jurisdiction": jurisdiction.upper(),
            "indexed_on": lib.today_iso(), "clauses": list(rows.values())}


def validate(index: dict, known_ids: set[str] | None = None) -> list[str]:
    errs = []
    if index.get("schema_version") != SCHEMA:
        errs.append(f"schema_version must be {SCHEMA}")
    if not index.get("contract"):
        errs.append("contract (file name) is required")
    for i, c in enumerate(index.get("clauses") or []):
        where = f"clauses[{i}] ({c.get('clause')})"
        if not c.get("clause"):
            errs.append(f"{where}: clause number is required ('-' for the whole contract)")
        if c.get("source") not in SOURCES:
            errs.append(f"{where}: source must be one of {list(SOURCES)}")
        if not c.get("acts"):
            errs.append(f"{where}: at least one act")
        for a in c.get("acts") or []:
            if not lib.ACT_ID_RE.match(str(a.get("id", ""))):
                errs.append(f"{where}: bad act id {a.get('id')!r}")
            elif known_ids is not None and a["id"] not in known_ids:
                errs.append(f"{where}: {a['id']} is neither in the catalog nor in the watchlist "
                            "(add it to the watchlist so its changes reach this clause)")
        if not isinstance(c.get("needs_reverify"), bool):
            errs.append(f"{where}: needs_reverify must be true or false")
    return errs


def load_all(profile: Path) -> dict[Path, dict]:
    folder = index_dir(profile)
    return {p: lib.read_json(p, "contract index") for p in sorted(folder.glob("*.json"))} if folder.exists() else {}


def save(profile: Path, index: dict, *, force: bool = False) -> Path:
    errs = validate(index)
    if errs:
        raise lib.WatchError("contract index: " + "; ".join(errs))
    path = index_dir(profile) / (Path(index["contract"]).stem + ".json")
    if path.exists() and not force:
        raise lib.WatchError(f"{path} exists; merge your changes into it or pass --force to replace it")
    lib.write_json(path, index)
    return path


def flag_changes(profile: Path, changes: list[dict]) -> list[dict]:
    """Mark every clause depending on a changed act; → one entry per contract with the flagged clauses."""
    if not changes:
        return []
    by_act = {c["act_id"]: c for c in changes}
    out = []
    for path, index in load_all(profile).items():
        hit = []
        for c in index.get("clauses") or []:
            for a in c.get("acts") or []:
                ch = by_act.get(a.get("id"))
                if ch is None:
                    continue
                entry = {"act_id": ch["act_id"], "kind": ch["kind"], "label": ch.get("label"),
                         "in_force_from": ch.get("in_force_from"), "run_date": ch["run_date"]}
                if entry not in c.setdefault("reverify", []):
                    c["reverify"].append(entry)
                c["needs_reverify"] = True
                hit.append(c["clause"])
        if hit:
            lib.write_json(path, index)
            out.append({"contract": index["contract"], "index": path.name, "clauses": sorted(set(hit))})
    return out


def pending(profile: Path) -> list[dict]:
    out = []
    for path, index in load_all(profile).items():
        flagged = [c for c in index.get("clauses") or [] if c.get("needs_reverify")]
        if flagged:
            out.append({"contract": index["contract"], "index": path.name,
                        "clauses": [{"clause": c["clause"], "reverify": c.get("reverify", [])} for c in flagged]})
    return out


def clear(profile: Path, contract: str, clause: str | None, matter: str) -> int:
    """After the re-review matter: clear the flags (one clause or all) and note the matter that handled them."""
    if not matter:
        raise lib.WatchError("--matter is required: a flag is cleared only by a re-review matter")
    path = index_dir(profile) / (Path(contract).stem + ".json")
    index = lib.read_json(path, "contract index")
    n = 0
    for c in index.get("clauses") or []:
        if c.get("needs_reverify") and (clause is None or c["clause"] == clause):
            c["needs_reverify"] = False
            c["reviewed"] = {"matter": matter, "on": lib.today_iso(), "changes": c.pop("reverify", [])}
            c["reverify"] = []
            n += 1
    if n == 0:
        raise lib.WatchError(f"no flagged clause {clause or ''} in {path.name}".replace("  ", " "))
    lib.write_json(path, index)
    return n
