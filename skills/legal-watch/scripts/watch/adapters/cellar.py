"""cellar: the fallback of eurlex through Cellar (Publications Office of the EU).

When EUR-Lex is behind its AWS WAF challenge (HTTP 202 / 403 with a challenge body → `blocked_403`) or does not
answer (`fetch_failed`), the same act is read from Cellar, the repository EUR-Lex is built from. The WAF is not
bypassed: Cellar is a separate official service of the Publications Office with an open API.

Two kinds of GET request, no keys:
1. metadata: SPARQL `https://publications.europa.eu/webapi/rdf/sparql` (CDM ontology):
   - `resource_legal_in-force`, `resource_legal_date_end-of-validity`, `resource_legal_date_entry-into-force`;
   - inverse links: consolidations (`act_consolidated_based_on_resource_legal`, CELEX `0<year><type><number>-YYYYMMDD`),
     repealing acts (`resource_legal_repeals_resource_legal`, `…implicitly_repeals…`), amending acts
     (`resource_legal_amends_resource_legal`), corrigenda (`…corrects…`) and proposals (`…proposes_to_amend…`);
2. text: `http://publications.europa.eu/resource/celex/<CELEX>` with `Accept: application/xhtml+xml`,
   `Accept-Language: ron`. For a consolidated act, the CELEX of the consolidation in force
   (`02016R0679-20160504`), else the base CELEX. The text gives the snapshot hash and the act identification.

Rules are those of eurlex: the version in force is the latest consolidation on or before the run date; without
consolidations, «forma de bază» from the first entry-into-force date; entry dates and an end of validity after the
run date are future versions (`next`), never in force; a pre-effect consolidation is folded into the base form
(`eurlex.fold_preeffect_consolidation`). Corrigenda and proposals go to the notes only: a proposal is not law,
and a corrigendum changes the text without a new consolidation.

Checked on live Cellar answers for two acts (fixtures `cellar-*.json`), so PARSER_CALIBRATED = True.
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from ..contract import (FETCH_FAILED, PARSE_FAILED, AdapterResult, Evidence, Redaction, classify, parse_date,
                        text_sha256)
from ..fetchers import USER_AGENT, now_iso
from . import eurlex

ADAPTER = "eurlex"
PARSER_ID = "eurlex/cellar-v1"
PARSER_CALIBRATED = True
RESOURCE_URL = "http://publications.europa.eu/resource/celex/{celex}"
SPARQL_URL = "https://publications.europa.eu/webapi/rdf/sparql"
TEXT_HEADERS = {"Accept": "application/xhtml+xml", "Accept-Language": "ron", "User-Agent": USER_AGENT}
SPARQL_HEADERS = {"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT}
MIN_TEXT_CHARS = 2000
NO_END = "9999-12-31"
TIMEOUT_S = 90

Q_FORWARD = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?p ?o WHERE {
  ?w cdm:resource_legal_id_celex ?c . FILTER(str(?c) = "%(celex)s")
  ?w ?p ?o .
  FILTER(?p IN (cdm:resource_legal_in-force, cdm:resource_legal_date_end-of-validity,
                cdm:resource_legal_date_entry-into-force, cdm:work_date_document))
}"""
Q_INVERSE = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT DISTINCT ?p ?sc WHERE {
  ?w cdm:resource_legal_id_celex ?c . FILTER(str(?c) = "%(celex)s")
  ?s ?p ?w .
  ?s cdm:resource_legal_id_celex ?sc .
  FILTER(?p IN (cdm:act_consolidated_based_on_resource_legal, cdm:resource_legal_repeals_resource_legal,
                cdm:resource_legal_implicitly_repeals_resource_legal, cdm:resource_legal_amends_resource_legal,
                cdm:resource_legal_corrects_resource_legal, cdm:resource_legal_proposes_to_amend_resource_legal))
}"""

# get(url, headers) -> (http_status, final_url, body_text); an exception is a network failure.
# A getter may carry a `via` attribute (engine name for the evidence); the default one is "urllib".
HttpGet = Callable[[str, dict], tuple]


class CellarError(RuntimeError):
    """Cellar answered, but not with usable metadata (HTTP error or unreadable JSON)."""


def urllib_get(url: str, headers: dict, timeout: float = TIMEOUT_S) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl(), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace") if e.fp else ""
        return e.code, url, body


urllib_get.via = "urllib"


def sparql_url(query: str) -> str:
    return SPARQL_URL + "?" + urllib.parse.urlencode({"query": query, "format": "application/sparql-results+json"})


def _local(uri: str) -> str:
    return uri.rsplit("#", 1)[-1]


def metadata(celex: str, get: HttpGet) -> dict:
    """→ {in_force, end, entry[], date_document, consolidations{date: celex}, repealed_by[], amended_by[],
    corrections[], proposals[], urls[], found}. HTTP or JSON trouble → CellarError."""
    out = {"in_force": None, "end": None, "entry": [], "date_document": None, "consolidations": {},
           "repealed_by": [], "amended_by": [], "corrections": [], "proposals": [], "urls": []}
    rows = {}
    for name, q in (("fwd", Q_FORWARD), ("inv", Q_INVERSE)):
        url = sparql_url(q % {"celex": celex})
        out["urls"].append(url)
        status, _final, body = get(url, SPARQL_HEADERS)
        if status != 200:
            raise CellarError(f"Cellar SPARQL HTTP {status}: {body[:200]!r}")
        try:
            rows[name] = json.loads(body)["results"]["bindings"]
        except (ValueError, KeyError, TypeError) as e:
            raise CellarError(f"Cellar SPARQL: unreadable answer ({type(e).__name__})") from e
    for b in rows["fwd"]:
        p, o = _local(b["p"]["value"]), b["o"]["value"]
        if p == "resource_legal_in-force":
            out["in_force"] = o.strip().lower() in ("1", "true")
        elif p == "resource_legal_date_end-of-validity":
            out["end"] = o[:10]
        elif p == "resource_legal_date_entry-into-force":
            out["entry"].append(o[:10])
        elif p == "work_date_document":
            out["date_document"] = o[:10]
    prefix = "0" + celex[1:] + "-"
    for b in rows["inv"]:
        p, sc = _local(b["p"]["value"]), b["sc"]["value"]
        if p == "act_consolidated_based_on_resource_legal" and sc.startswith(prefix):
            try:
                d = _dt.datetime.strptime(sc[len(prefix):len(prefix) + 8], "%Y%m%d").date()
            except ValueError:
                continue
            out["consolidations"][d.isoformat()] = sc
        elif p in ("resource_legal_repeals_resource_legal", "resource_legal_implicitly_repeals_resource_legal"):
            out["repealed_by"].append(sc)
        elif p == "resource_legal_amends_resource_legal":
            out["amended_by"].append(sc)
        elif p == "resource_legal_corrects_resource_legal":
            out["corrections"].append(sc)
        elif p == "resource_legal_proposes_to_amend_resource_legal":
            out["proposals"].append(sc)
    for k in ("entry", "repealed_by", "amended_by", "corrections", "proposals"):
        out[k] = sorted(set(out[k]))
    out["found"] = bool(rows["fwd"])
    return out


def redactions_from(meta: dict, act: dict, celex: str, today: _dt.date) -> dict:
    """Cellar metadata → the same shape as eurlex.parse_eurlex (redactions, mode, notes, repealed…)."""
    p = {"repealed": False, "repealed_label": None, "redactions": [], "mode": "none", "notes": [],
         "effects": list(meta["entry"])}
    end = parse_date(meta.get("end")) if meta.get("end") and meta.get("end") != NO_END else None
    if (end is not None and end <= today) or (meta.get("in_force") is False and meta["repealed_by"]):
        by = ", ".join(meta["repealed_by"]) or None
        p["repealed"] = True
        p["repealed_label"] = (f"abrogat{' de ' + by if by else ''}"
                               f"{' (sfârșitul valabilității ' + f'{end:%d.%m.%Y}' + ')' if end else ''}")
        p["mode"] = "cellar-no-longer-in-force"
        return p
    cons = [Redaction(label=f"consolidare {_dt.date.fromisoformat(d):%d.%m.%Y}", in_force_from=d, doc_id=c)
            for d, c in sorted(meta["consolidations"].items())]
    future = [Redaction(label=f"aplicare {_dt.date.fromisoformat(d):%d.%m.%Y} (date of entry into force, Cellar)",
                        in_force_from=d) for d in meta["entry"] if _dt.date.fromisoformat(d) > today]
    if end is not None and end > today:
        future.append(Redaction(label=f"sfârșitul valabilității {end:%d.%m.%Y}", in_force_from=end.isoformat()))
    past_entry = [d for d in meta["entry"] if _dt.date.fromisoformat(d) <= today]
    if cons:
        p["redactions"] = cons + future
        p["mode"] = "cellar-consolidations"
        eurlex_mode = dict(p, mode="consolidations")
        eurlex.fold_preeffect_consolidation(eurlex_mode, act, celex)
        p["redactions"], p["notes"] = eurlex_mode["redactions"], eurlex_mode["notes"]
        if eurlex_mode["mode"] != "consolidations":
            p["mode"] = "cellar-" + eurlex_mode["mode"]
    elif past_entry:
        p["redactions"] = [Redaction(label="forma de bază", in_force_from=min(past_entry), doc_id=celex)] + future
        p["mode"] = "cellar-base-form"
    else:
        p["redactions"] = future
        p["mode"] = "cellar-future-only" if future else "cellar-none"
    if meta.get("in_force") is False:
        p["notes"].append("Cellar resource_legal_in-force = 0 without a past end of validity")
    if meta["amended_by"]:
        p["notes"].append("amending acts (Cellar): " + ", ".join(meta["amended_by"]))
    if meta["corrections"]:
        p["notes"].append("corrigenda (Cellar; the text changes without a new consolidation): "
                          + ", ".join(meta["corrections"]))
    if meta["proposals"]:
        p["notes"].append("amendment proposals (drafts, they do not change the law): " + ", ".join(meta["proposals"]))
    return p


def page_text(body: str) -> tuple[str, str]:
    """Cellar XHTML → (title, plain text)."""
    m = re.search(r"<title>(.*?)</title>", body or "", re.S | re.I)
    title = _html.unescape(m.group(1)).strip() if m else ""
    t = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", body or "")
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return title, re.sub(r"\s+", " ", _html.unescape(t)).strip()


def identifies(celex: str, text: str) -> bool:
    year, num = eurlex.year_number(celex)
    return bool(re.search(rf"(?<![\d/]){year}/{num}(?!\d)", (text or "")[:8000]))


def check_act(act: dict, today: _dt.date, *, get: HttpGet | None = None,
              primary_error: str | None = None) -> AdapterResult:
    get = get or urllib_get
    via = getattr(get, "via", "urllib")
    act_id = act["id"]
    celex = eurlex.celex_of(act)
    pre = [f"EUR-Lex primary failed: {primary_error}; read via Cellar (Publications Office)"] if primary_error else []
    if celex is None:
        return AdapterResult(act_id=act_id, adapter=ADAPTER, status=FETCH_FAILED, notes=pre,
                             error="act has no eurlex source with a CELEX or ELI").validate()
    fetched_at = now_iso()
    meta_ev = Evidence(url=SPARQL_URL, fetched_at=fetched_at, parser=PARSER_ID, parser_calibrated=PARSER_CALIBRATED,
                       via=via)
    try:
        meta = metadata(celex, get)
    except Exception as e:  # noqa: BLE001 — any Cellar failure means "not verified"
        return AdapterResult(act_id=act_id, adapter=ADAPTER, status=FETCH_FAILED, notes=pre, evidence=meta_ev,
                             error=f"Cellar: {type(e).__name__}: {str(e)[:240]}").validate()
    if not meta["found"]:
        return AdapterResult(act_id=act_id, adapter=ADAPTER, status=PARSE_FAILED, notes=pre, evidence=meta_ev,
                             error=f"Cellar SPARQL: no work with CELEX {celex}").validate()
    p = redactions_from(meta, act, celex, today)

    # The text: CELEX of the consolidation in force, else the base CELEX.
    in_force = sorted((r for r in p["redactions"] if r.in_force_from
                       and _dt.date.fromisoformat(r.in_force_from) <= today), key=lambda r: r.in_force_from)
    cur_celex = in_force[-1].doc_id if in_force and in_force[-1].doc_id else celex
    tried, status, final_url, body, used = [], None, None, "", None
    for c in dict.fromkeys([cur_celex, celex]):
        url = used = RESOURCE_URL.format(celex=c)
        tried.append(url)
        try:
            status, final_url, body = get(url, TEXT_HEADERS)
        except Exception as e:  # noqa: BLE001
            status, final_url, body = None, url, ""
            pre.append(f"Cellar text {c}: {type(e).__name__}: {str(e)[:160]}")
            continue
        if status == 200 and len(body) >= MIN_TEXT_CHARS:
            break
        pre.append(f"Cellar text {c}: HTTP {status}, {len(body)} bytes")
    _title, text = page_text(body)
    ev = Evidence(url=used, fetched_at=fetched_at, http_status=status, sha256=text_sha256(text) if text else None,
                  parser=f"{PARSER_ID}:{p['mode']}", parser_calibrated=PARSER_CALIBRATED, via=via)
    notes = pre + [f"cellar_text: {final_url}", f"cellar_sparql: {SPARQL_URL}"]

    def fail(st, err):
        return AdapterResult(act_id=act_id, adapter=ADAPTER, status=st, evidence=ev, error=err,
                             notes=notes).validate()

    if status != 200:
        return fail(FETCH_FAILED, f"Cellar text not delivered (HTTP {status}) for {', '.join(tried)}")
    if len(text) < MIN_TEXT_CHARS:
        return fail(PARSE_FAILED, f"Cellar text too short ({len(text)} chars)")
    if not identifies(celex, text):
        return fail(PARSE_FAILED, f"Cellar text does not identify {celex}")
    if not p["repealed"] and not p["redactions"]:
        return fail(PARSE_FAILED, "Cellar: no consolidation or entry-into-force date")
    st, cur, nxt, err, cnotes = classify(act=act, parsed=p["redactions"], today=today,
                                         repealed=p["repealed"], repealed_label=p["repealed_label"])
    return AdapterResult(act_id=act_id, adapter=ADAPTER, status=st, current=cur, next=nxt, evidence=ev,
                         error=err, notes=notes + p["notes"] + cnotes).validate()
