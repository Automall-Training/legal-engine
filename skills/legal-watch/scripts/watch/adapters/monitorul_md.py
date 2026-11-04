"""monitorul_md: new issues of the Official Gazette of Moldova (monitorul.gov.md).

A signal source, not a version check: a watched act named in the table of contents of a new issue gives a
`Signal`. Deciding that the act changed is not this module's job (legis_md, the user or an impact review does
that), so the result is a `contract.SourceScan` and no act gets a status.

How the site is built (checked against live pages, snapshots in tests/fixtures/monitorul_md):
- home `https://monitorul.gov.md/ro`: the "Edițiile recente" carousel, links `/ro/monitor/<id>` with «Monitorul
  Oficial Nr. 481-482» and «din 24.09.2026»; ids grow by 1;
- issue page `/ro/monitor/<id>`: `<h2>Monitorul Oficial Nr. …</h2>` and the table of contents in
  `<div class="release-intro-text">`: lines «496. Lege pentru modificarea … (nr. 211, 17 septembrie 2026)».

Not ported: the deep check of the issue PDF. Omnibus laws («Lege pentru modificarea unor acte normative») do not
name the acts they amend in the table of contents, so an omnibus law that does not name the watched act in its
title gives NO signal here. Watching the act's own page (legis_md) still catches the new version.

The pass: from `since` (the last issue checked without gaps) to the newest id on the home page, every id in a row;
the first failure stops `checked_through`, so no issue is ever skipped silently. `since=None` (first run) is a
baseline pass over the issues visible on the home page; it shows as `previous_checked_through=None`. A missing id
inside the range (404) is fetch_failed, not a skip. GET only; anti-bot pages are reported, never bypassed.
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import re

from ..contract import (BLOCKED_403, FETCH_FAILED, PARSE_FAILED, SCAN_COMPLETE, Edition, Evidence, Signal,
                        SourceScan, act_number_year, text_sha256)
from ..fetchers import Fetcher

SOURCE = "monitorul_md"
PARSER_ID = "monitorul_md/v1"
PARSER_CALIBRATED = True
BASE = "https://monitorul.gov.md"
HOME_URL = BASE + "/ro"
EDITION_URL = BASE + "/ro/monitor/{id}"
MAX_EDITIONS_PER_RUN = 40

CAROUSEL_RE = re.compile(
    r'href="(?:https://monitorul\.gov\.md)?/ro/monitor/(?P<id>\d+)"[^>]*>\s*<div[^>]*>\s*'
    r"<h4>\s*Monitorul Oficial Nr\.\s*(?P<num>[^<]+?)\s*</h4>\s*"
    r'<span[^>]*>\s*din\s+(?P<date>\d{2}\.\d{2}\.\d{4})\s*</span>', re.S)
H2_RE = re.compile(r"<h2>\s*Monitorul Oficial Nr\.\s*(?P<num>[^<]+?)\s*</h2>", re.S)
INTRO_RE = re.compile(r'<div class="release-intro-text">(?P<body>.*?)</div>\s*</div>\s*<div class="release-see-more',
                      re.S)
ITEM_RE = re.compile(r"^\s*(?P<n>\d+[a-z]?)\.\s+(?P<t>\S.*)$")
RO_MONTHS = {m: i for i, m in enumerate(
    ["ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie", "august",
     "septembrie", "octombrie", "noiembrie", "decembrie"], start=1)}
DATE_LONG_RE = re.compile(r"(?:Luni|Marți|Marţi|Miercuri|Joi|Vineri|Sâmbătă|Duminică),\s*(\d{1,2})\s+([a-zăâîșşțţ]+)\s+(\d{4})",
                          re.I)

# Moldovan codes are named in the table of contents by their name, not always by number/year.
# act["code"] → regex of the name (any grammatical case: «Codul muncii», «Codului muncii»).
MD_CODE_NAMES = {"muncii": r"Codul(?:ui)?\s+muncii", "fiscal": r"Codul(?:ui)?\s+fiscal",
                 "civil": r"Codul(?:ui)?\s+civil", "familiei": r"Codul(?:ui)?\s+familiei"}


def parse_home(html: str) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for m in CAROUSEL_RE.finditer(html or ""):
        d = m.group("date")
        out[int(m.group("id"))] = {"number": m.group("num").strip(), "date": f"{d[6:]}-{d[3:5]}-{d[:2]}"}
    return out


def parse_edition(html: str, text: str) -> tuple[str | None, str | None, list[str]] | None:
    """→ (issue number, ISO date, table-of-contents lines), or None when the page structure is not recognised."""
    h2 = H2_RE.search(html or "")
    intro = INTRO_RE.search(html or "")
    if not h2 or not intro:
        return None
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", intro.group("body"))
    body = re.sub(r"(?i)<br\s*/?>|</div>|</p>|</h\d>", "\n", body)
    body = _html.unescape(re.sub(r"(?s)<[^>]+>", "", body)).replace("\xa0", " ")
    items = [re.sub(r"\s+", " ", ln).strip() for ln in body.splitlines() if ITEM_RE.match(ln)]
    date = None
    m = DATE_LONG_RE.search(text or "")
    if m and m.group(2).lower() in RO_MONTHS:
        try:
            date = _dt.date(int(m.group(3)), RO_MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
        except ValueError:
            date = None
    return h2.group("num").strip(), date, items


def act_patterns(act: dict) -> list[re.Pattern]:
    """How to recognise the act in a table-of-contents line. Moldovan acts only; an empty list = not searched."""
    if act.get("jurisdiction") != "MD":
        return []
    pats: list[re.Pattern] = []
    ny = act_number_year(act)
    if ny:
        num, year = ny
        pats.append(re.compile(rf"(?<![\d/]){num}(?:-[IVXL]+)?\s*/\s*{year}(?!\d)"))
        pats.append(re.compile(rf"nr\.\s*{num}(?:-[IVXL]+)?\s+din\s+[^)]{{0,30}}?{year}", re.I))
    code = str(act.get("code") or "")
    if code in MD_CODE_NAMES:
        pats.append(re.compile(MD_CODE_NAMES[code], re.I))
    return pats


def match_act(item: str, pats: list[re.Pattern]) -> str | None:
    for p in pats:
        m = p.search(item)
        if m:
            return m.group(0)
    return None


def scan(acts: list[dict], fetcher: Fetcher, since: int | None, today: _dt.date,
         max_editions: int = MAX_EDITIONS_PER_RUN) -> SourceScan:
    home = fetcher.get(HOME_URL)
    ev = Evidence(url=HOME_URL, fetched_at=home.fetched_at, http_status=home.status,
                  sha256=text_sha256(home.text) if home.text else None, parser=PARSER_ID,
                  parser_calibrated=PARSER_CALIBRATED, via=home.via)

    def result(status, checked, latest, editions, signals, err):
        return SourceScan(source=SOURCE, status=status, checked_through=checked,
                          previous_checked_through=since, latest_seen=latest, editions=editions,
                          signals=signals, evidence=ev, error=err).validate()

    if home.error:
        return result(FETCH_FAILED, since, None, [], [], home.error)
    if home.blocked:
        return result(BLOCKED_403, since, None, [], [], f"{home.blocked_reason}; not bypassed")
    if home.status is None or home.status >= 400:
        return result(FETCH_FAILED, since, None, [], [], f"HTTP {home.status}")
    recent = parse_home(home.html)
    if not recent:
        return result(PARSE_FAILED, since, None, [], [], "home page: no recent editions recognised")
    latest = max(recent)
    if since is not None and latest < since:
        return result(PARSE_FAILED, since, latest, [], [],
                      f"latest edition on home ({latest}) is older than checked_through ({since})")

    ids = list(range(since + 1, latest + 1)) if since is not None else sorted(recent)
    truncated = len(ids) > max_editions
    ids = ids[:max_editions]

    tracked = [(a, act_patterns(a)) for a in acts]
    tracked = [(a, p) for a, p in tracked if p]
    editions: list[Edition] = []
    signals: list[Signal] = []
    checked = since
    for eid in ids:
        url = EDITION_URL.format(id=eid)
        r = fetcher.get(url)
        fail = None
        if r.error:
            fail = (FETCH_FAILED, f"edition {eid}: {r.error}")
        elif r.blocked:
            fail = (BLOCKED_403, f"edition {eid}: {r.blocked_reason}; not bypassed")
        elif r.status is None or r.status >= 400:
            fail = (FETCH_FAILED, f"edition {eid}: HTTP {r.status}")
        parsed = None if fail else parse_edition(r.html, r.text)
        if not fail and parsed is None:
            fail = (PARSE_FAILED, f"edition {eid}: page structure not recognised")
        if fail:
            return result(fail[0], checked, latest, editions, signals, fail[1])
        num, date, items = parsed
        meta = recent.get(eid, {})
        num = num or meta.get("number")
        date = date or meta.get("date")
        editions.append(Edition(edition_id=eid, number=num, date=date, url=url,
                                sha256=text_sha256("\n".join(items)), items=len(items)))
        for item in items:
            for a, pats in tracked:
                hit = match_act(item, pats)
                if hit:
                    signals.append(Signal(act_id=a["id"], edition_id=eid, edition_number=num,
                                          edition_date=date, item=item, matched=hit, url=url))
        checked = eid if checked is None or eid > checked else checked
    if truncated:
        return result(FETCH_FAILED, checked, latest, editions, signals,
                      f"more than {max_editions} new editions; stopped at {checked}, continue next run")
    return result(SCAN_COMPLETE, checked, latest, editions, signals, None)
