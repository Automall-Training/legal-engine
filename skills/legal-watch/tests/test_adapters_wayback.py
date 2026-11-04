"""wayback adapter: always stale_fallback; a snapshot older than 14 days is fetch_failed "not verified". No network."""
import dataclasses
import datetime as dt
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from watch.adapters import just_ro, wayback  # noqa: E402
from watch.contract import (BLOCKED_403, FETCH_FAILED, PARSE_FAILED, STALE_FALLBACK, UNCHANGED,  # noqa: E402
                            UNVERIFIED)
from watch.fetchers import FetchResult, FixtureFetcher, fixture_result  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
T = dt.date(2026, 9, 28)
ORIG = just_ro.PAGE_URL.format(doc_id="158913")
PAGE = "just_ro/oug34-consolidated-wb20251217.html"


def read(rel: str) -> str:
    return (FIX / rel).read_text(encoding="utf-8")


def act(label="consolidare 20.07.2022", date="2022-07-20"):
    return {"id": "ro.oug.34-2014", "jurisdiction": "RO", "priority": "p1",
            "current": {"label": label, "in_force_from": date}, "next": None,
            "sources": [{"kind": "just_ro", "doc_id": "158913"}]}


def snap(html, ts, *, status=200, today=T):
    """A FetchResult as an engine returns it after Wayback redirected to snapshot `ts`."""
    req = wayback.snapshot_url(ORIG, today)
    r = fixture_result(req, html, status=status)
    return req, dataclasses.replace(r, final_url=f"https://web.archive.org/web/{ts}id_/{ORIG}")


def run(a, html, ts, *, status=200, today=T):
    req, r = snap(html, ts, status=status, today=today)
    return wayback.check_act(a, FixtureFetcher({req: r}), today)


class Snapshot(unittest.TestCase):
    def test_fresh_matching_snapshot_is_stale_fallback_never_unchanged(self):
        res = run(act(), read(PAGE), "20260920101010")
        self.assertEqual(res.status, STALE_FALLBACK)
        self.assertIn("snapshot classification: unchanged", res.notes)
        self.assertIn("wayback_snapshot: 2026-09-20T10:10:10Z", res.notes)
        self.assertIn("/web/20260920101010id_/", res.evidence.url)
        self.assertEqual(res.current.label, "consolidare 20.07.2022")
        self.assertTrue(res.evidence.parser_calibrated)
        self.assertEqual(res.evidence.via, "fixture")
        self.assertIn(STALE_FALLBACK, UNVERIFIED)

    def test_fresh_snapshot_with_new_consolidation_is_still_stale_fallback(self):
        res = run(act(), read("just_ro/new-in-force.html"), "20260927000000")
        self.assertEqual(res.status, STALE_FALLBACK)
        self.assertIn("snapshot classification: new_in_force", res.notes)
        self.assertEqual(res.current.label, "consolidare 15.09.2026")

    def test_fresh_snapshot_with_future_version_keeps_next(self):
        res = run(act(), read("just_ro/new-future.html"), "20260927000000")
        self.assertEqual(res.status, STALE_FALLBACK)
        self.assertEqual(res.next.in_force_from, "2027-01-15")

    def test_snapshot_older_than_14_days_is_not_verified(self):
        res = run(act(), read(PAGE), "20251217000637")
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertIn("not verified", res.error)
        self.assertIn("2025-12-17", res.error)

    def test_exactly_14_days_accepted_15_not(self):
        self.assertEqual(run(act(), read(PAGE), "20260914000000").status, STALE_FALLBACK)
        self.assertEqual(run(act(), read(PAGE), "20260913235959").status, FETCH_FAILED)

    def test_snapshot_later_than_today_is_parse_failed(self):
        self.assertEqual(run(act(), read(PAGE), "20260930000000").status, PARSE_FAILED)

    def test_wayback_offline_503_is_fetch_failed(self):
        res = run(act(), read("wayback/offline-503-2026-09-27.html"), "20260927000000", status=503)
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertIn("503", res.error)

    def test_wayback_network_error_is_fetch_failed(self):
        req = wayback.snapshot_url(ORIG, T)
        r = FetchResult(url=req, status=None, fetched_at="t", error="TimeoutError: timed out")
        self.assertEqual(wayback.check_act(act(), FixtureFetcher({req: r}), T).status, FETCH_FAILED)

    def test_wayback_blocked_is_blocked_403(self):
        res = run(act(), read("legis_md/cloudflare-challenge-2026-09-27.html"), "20260927000000", status=403)
        self.assertEqual(res.status, BLOCKED_403)
        self.assertTrue(res.error.startswith("Wayback:"))

    def test_unreadable_timestamp_is_parse_failed(self):
        req = wayback.snapshot_url(ORIG, T)
        r = dataclasses.replace(fixture_result(req, read(PAGE)), final_url="https://web.archive.org/whatever")
        self.assertEqual(wayback.check_act(act(), FixtureFetcher({req: r}), T).status, PARSE_FAILED)
        self.assertIsNone(wayback.snapshot_time("https://web.archive.org/web/20261399000000id_/x"))

    def test_no_redirect_reported_is_parse_failed_not_fresh(self):
        # An engine that keeps final_url = requested URL would make any copy look like today's.
        req = wayback.snapshot_url(ORIG, T)
        res = wayback.check_act(act(), FixtureFetcher({req: fixture_result(req, read(PAGE))}), T)
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertIn("no redirect", res.error)

    def test_snapshot_of_wrong_page_is_parse_failed(self):
        self.assertEqual(run(act(), read("just_ro/oug141-base-wb20251212.html"), "20260927000000").status,
                         PARSE_FAILED)

    def test_truncated_snapshot_is_parse_failed(self):
        self.assertEqual(run(act(), read("just_ro/truncated.html"), "20260927000000").status, PARSE_FAILED)

    def test_snapshot_older_than_baseline_is_parse_failed(self):
        self.assertEqual(run(act("consolidare 15.09.2026", "2026-09-15"), read(PAGE), "20260927000000").status,
                         PARSE_FAILED)

    def test_act_without_just_ro_source(self):
        a = dict(act(), sources=[])
        res = wayback.check_act(a, FixtureFetcher({}), T, primary_error="x")
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertIn("primary just_ro failed: x", res.notes)


PORTAL_DOWN = FetchResult(url=ORIG, status=None, fetched_at="2026-09-28T07:00:00Z",
                          error="URLError: HTTP/2 protocol error")


def chain(primary, wb):
    m = {ORIG: primary}
    if wb is not None:
        m[wb[0]] = wb[1]
    f = FixtureFetcher(m)
    return wayback.check_with_fallback(act(), f, T), f


class Fallback(unittest.TestCase):
    def test_portal_down_fresh_snapshot_is_stale_fallback(self):
        res, f = chain(PORTAL_DOWN, snap(read(PAGE), "20260926000000"))
        self.assertEqual(res.status, STALE_FALLBACK)
        self.assertEqual(res.adapter, "wayback")
        self.assertTrue(any("HTTP/2" in n for n in res.notes))
        self.assertEqual(len(f.calls), 2)

    def test_portal_down_old_snapshot_stays_fetch_failed(self):
        res, _ = chain(PORTAL_DOWN, snap(read(PAGE), "20251217000637"))
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertEqual(res.adapter, "just_ro")
        self.assertTrue(any("not verified" in n for n in res.notes))
        self.assertTrue(any(n.startswith("wayback_snapshot: 2025-12-17") for n in res.notes))

    def test_portal_blocked_uses_wayback(self):
        blocked = fixture_result(ORIG, read("legis_md/cloudflare-challenge-2026-09-27.html"), status=403)
        res, _ = chain(blocked, snap(read(PAGE), "20260926000000"))
        self.assertEqual(res.status, STALE_FALLBACK)

    def test_portal_ok_does_not_touch_wayback(self):
        res, f = chain(fixture_result(ORIG, read(PAGE)), None)
        self.assertEqual(res.status, UNCHANGED)
        self.assertEqual(f.calls, [ORIG])

    def test_portal_parse_failed_is_not_masked(self):
        res, f = chain(fixture_result(ORIG, read("just_ro/no-dates.html")), snap(read(PAGE), "20260926000000"))
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertEqual(f.calls, [ORIG])

    def test_both_down_is_fetch_failed(self):
        req = wayback.snapshot_url(ORIG, T)
        res, _ = chain(PORTAL_DOWN, (req, FetchResult(url=req, status=None, fetched_at="x", error="Timeout")))
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertTrue(any("wayback fallback: fetch_failed" in n for n in res.notes))

    def test_no_source_returns_primary(self):
        a = dict(act(), sources=[])
        res = wayback.check_with_fallback(a, FixtureFetcher({}), T)
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertEqual(res.adapter, "just_ro")


if __name__ == "__main__":
    unittest.main()
