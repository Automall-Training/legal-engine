"""wayback: the fallback source for legislatie.just.ro (web.archive.org).

When the portal cannot be read (fetch_failed / blocked_403), the latest Wayback Machine copy of the same page is
read with one GET:
  https://web.archive.org/web/<today>235959id_/https://legislatie.just.ro/Public/DetaliiDocument/<id>
Wayback redirects to the nearest (latest) snapshot; its timestamp is taken from the final URL
(`/web/20251217000637id_/`). `id_` returns the portal's answer byte for byte, so the parser is the same
`just_ro.parse_just_html`.

Rules:
- the result is ALWAYS `stale_fallback` (never `unchanged`), even when the snapshot matches the baseline: an
  archive copy is not the official portal on the run date. The snapshot time is in evidence.url and in the notes
  (`wayback_snapshot: …`);
- a snapshot older than 14 days gives `fetch_failed` ("not verified");
- an unreadable snapshot or a snapshot of another act gives `parse_failed`; Wayback down gives `fetch_failed`.

The parser was checked on live Wayback answers for four acts, so PARSER_CALIBRATED = True. The CDX API answered
503 at the time and is not used.
"""
from __future__ import annotations

import datetime as _dt
import re

from ..contract import BLOCKED_403, FETCH_FAILED, PARSE_FAILED, STALE_FALLBACK, AdapterResult, classify
from ..fetchers import Fetcher
from . import just_ro

ADAPTER = "wayback"
PARSER_ID = "wayback+just_ro/html-v1"
PARSER_CALIBRATED = True
MAX_AGE_DAYS = 14
SNAPSHOT_URL = "https://web.archive.org/web/{ts}id_/{orig}"
TS_RE = re.compile(r"/web/(?P<ts>\d{14})(?:id_)?/")


def snapshot_url(orig: str, today: _dt.date) -> str:
    return SNAPSHOT_URL.format(ts=f"{today:%Y%m%d}235959", orig=orig)


def snapshot_time(final_url: str | None) -> _dt.datetime | None:
    m = TS_RE.search(final_url or "")
    if not m:
        return None
    try:
        return _dt.datetime.strptime(m.group("ts"), "%Y%m%d%H%M%S").replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


def check_act(act: dict, fetcher: Fetcher, today: _dt.date, *, primary_error: str | None = None,
              max_age_days: int = MAX_AGE_DAYS) -> AdapterResult:
    act_id = act["id"]
    doc_id, orig = just_ro.page_source(act)
    pre = [f"primary just_ro failed: {primary_error}"] if primary_error else []
    if orig is None:
        return AdapterResult(act_id=act_id, adapter=ADAPTER, status=FETCH_FAILED, notes=pre,
                             error="act has no just_ro source with a doc_id").validate()
    url = snapshot_url(orig, today)
    r = fetcher.get(url)
    failed, page, ev = just_ro.result_from_fetch(act, r, today, adapter=ADAPTER, url=url,
                                                 doc_id=doc_id, parser_id=PARSER_ID,
                                                 calibrated=PARSER_CALIBRATED)
    # The requested URL carries today's date; only the redirect target names the real snapshot. An engine that
    # does not report redirects (final_url == requested URL) would make any copy look fresh, so it counts as unknown.
    snap = snapshot_time(r.final_url) if r.final_url and r.final_url != url else None
    if snap is not None:
        ev.url = r.final_url                     # the snapshot timestamp lives in the evidence URL
    if failed is not None:
        failed.notes = pre + failed.notes
        if failed.status == BLOCKED_403:
            failed.error = f"Wayback: {failed.error}"
        return failed

    def fail(status, err, extra=()):
        return AdapterResult(act_id=act_id, adapter=ADAPTER, status=status, evidence=ev,
                             error=err, notes=pre + list(extra)).validate()

    if snap is None:
        return fail(PARSE_FAILED, f"cannot read the Wayback snapshot timestamp from the final URL {r.final_url!r} "
                                  "(no redirect reported by the fetch engine)")
    snap_note = f"wayback_snapshot: {snap.isoformat().replace('+00:00', 'Z')}"
    age = (today - snap.date()).days
    if age < 0:
        return fail(PARSE_FAILED, f"Wayback snapshot {snap.date()} is later than today {today}", [snap_note])
    if age > max_age_days:
        return fail(FETCH_FAILED, f"not verified: Wayback snapshot of {snap.date()} is older than "
                                  f"{max_age_days} days ({age} d); the official portal was not read",
                    [snap_note])

    status, cur, nxt, err, notes = classify(act=act, parsed=page.redactions, today=today,
                                            repealed=page.repealed, repealed_label=page.repealed_by)
    if status == PARSE_FAILED:
        return fail(PARSE_FAILED, f"Wayback snapshot {snap.date()}: {err}", [snap_note] + notes)
    notes = pre + [snap_note, f"snapshot age {age} d", f"snapshot classification: {status}"] \
        + page.notes + notes
    return AdapterResult(act_id=act_id, adapter=ADAPTER, status=STALE_FALLBACK, current=cur, next=nxt,
                         evidence=ev,
                         error=f"fallback source (Wayback snapshot {snap.date()}), official portal not read",
                         notes=notes).validate()


def check_with_fallback(act: dict, fetcher: Fetcher, today: _dt.date) -> AdapterResult:
    """just_ro, and on fetch_failed / blocked_403 the Wayback copy.

    A parse_failed of the portal is NOT replaced by a copy: it means the parser needs fixing. When Wayback gives
    no stale_fallback either, the just_ro result stays and the Wayback outcome goes to its notes (a failure stays
    a failure).
    """
    primary = just_ro.check_act(act, fetcher, today)
    if primary.status not in (FETCH_FAILED, BLOCKED_403) or just_ro.page_source(act)[1] is None:
        return primary
    fb = check_act(act, fetcher, today, primary_error=primary.error)
    if fb.status == STALE_FALLBACK:
        return fb
    primary.notes.append(f"wayback fallback: {fb.status}: {fb.error}")
    primary.notes.extend(n for n in fb.notes if n.startswith("wayback_snapshot"))
    return primary.validate()
