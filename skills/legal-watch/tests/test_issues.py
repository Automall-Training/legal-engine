"""The monitoring error log: failures are kept across runs, a check closes them, engines that keep failing on a
site are tried last, and nothing is written inside the engine folder."""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_runner import TODAY, V1, RunnerBase, act, adapter, card  # noqa: E402
from watch import issues, library as lib, manual, runner  # noqa: E402
from watch.fetchers import ChainFetcher, FetchResult  # noqa: E402


class Log(RunnerBase):
    def log(self):
        return issues.load(self.profile)

    def test_failure_is_logged_with_detail(self):
        self.run_with([act()], adapter([V1], fail="blocked_403"))
        e = self.log()["acts"]["ro.lege.1-2020"]
        self.assertEqual((e["state"], e["kind"], e["count"], e["streak"]), ("open", "blocked", 1, 1))
        self.assertEqual(e["last"]["url"], "https://official.example/act")
        self.assertEqual(e["last"]["via"], "urllib")
        self.assertEqual(e["host"], "official.example")
        self.assertEqual(e["last"]["error"], "site down")

    def test_second_run_of_the_day_keeps_the_first_failure(self):
        self.run_with([act()], adapter([V1], fail="fetch_failed"))
        self.run_with([act()], adapter([V1], fail="parse_failed"))
        e = self.log()["acts"]["ro.lege.1-2020"]
        self.assertEqual([h["kind"] for h in e["history"]], ["fetch_failed", "parse_failed"])
        self.assertEqual(e["count"], 2)

    def test_check_closes_the_issue(self):
        self.run_with([act()], adapter([V1], fail="fetch_failed"))
        self.run_with([act()], adapter([V1]))
        e = self.log()["acts"]["ro.lege.1-2020"]
        self.assertEqual((e["state"], e["resolved_on"], e["resolved_by"]), ("resolved", TODAY.isoformat(),
                                                                            "checked by a run"))
        self.assertEqual(issues.open_issues(self.log()), [])

    def test_new_failure_after_resolution_opens_a_fresh_issue(self):
        self.run_with([act()], adapter([V1], fail="fetch_failed"))
        self.run_with([act()], adapter([V1]))
        self.run_with([act()], adapter([V1], fail="blocked_403"))
        e = self.log()["acts"]["ro.lege.1-2020"]
        self.assertEqual((e["state"], e["count"], e["kind"]), ("open", 1, "blocked"))

    def test_partial_run_does_not_touch_other_acts(self):
        a, b = act(), act("ro.lege.2-2020")
        self.run_with([a, b], adapter([V1], fail="fetch_failed"))
        self.run_with([a, b], adapter([V1]), selector="ro.lege.1-2020")
        log = self.log()
        self.assertEqual(log["acts"]["ro.lege.2-2020"]["state"], "open")
        self.assertEqual(log["acts"]["ro.lege.2-2020"]["count"], 1)

    def test_no_source_and_uncalibrated_kinds(self):
        self.run_with([act()], adapter([V1], calibrated=False))
        with mock.patch.object(runner, "adapter_for", lambda a: ("none", None)):
            runner.run(self.profile, [act("ro.lege.2-2020")], None, TODAY, scan_gazette=False)
        log = self.log()["acts"]
        self.assertEqual(log["ro.lege.1-2020"]["kind"], "uncalibrated")
        self.assertEqual(log["ro.lege.2-2020"]["kind"], "no_source")

    def test_dry_run_writes_no_log(self):
        self.run_with([act()], adapter([V1], fail="fetch_failed"), dry_run=True)
        self.assertFalse(issues.path(self.profile).exists())

    def test_hand_check_closes_the_issue(self):
        self.run_with([act()], adapter([V1], fail="blocked_403"))
        checker = mock.Mock()
        checker.load.return_value = card()
        checker.validate.return_value = {"errors": []}
        with mock.patch.object(manual, "_checker", return_value=checker):
            manual.record(self.profile, [act()], Path("card.json"), TODAY)
        e = self.log()["acts"]["ro.lege.1-2020"]
        self.assertEqual((e["state"], e["resolved_by"]), ("resolved", "checked by hand"))

    def test_resolved_entries_expire(self):
        log = issues.empty()
        issues.update_acts(log, [{"act_id": "x", "reasons": ["fetch_failed"]}], set(), "2026-01-01", "t")
        issues.update_acts(log, [], {"x"}, "2026-01-02", "t")
        issues.update_acts(log, [], set(), "2026-06-01", "t")
        self.assertNotIn("x", log["acts"])

    def test_expected_work_is_not_an_error(self):
        self.assertIsNone(issues.kind_of(["host_only"]))
        self.assertIsNone(issues.kind_of(["gazette_signal"]))
        self.assertEqual(issues.kind_of(["gazette_signal", "parse_failed"]), "parse_failed")
        self.assertEqual(issues.kind_of(["something_new"]), "something_new")

    def test_schema_is_checked(self):
        lib.write_json(issues.path(self.profile), {"schema_version": 99})
        with self.assertRaises(lib.WatchError):
            issues.load(self.profile)

    def test_never_written_inside_the_engine(self):
        with self.assertRaises(lib.WatchError):
            issues.save(lib.ENGINE_ROOT, issues.empty())


def fail(via, host="site.example"):
    return {"host": host, "via": via, "ok": False, "error": "HTTP 403"}


class Engines(unittest.TestCase):
    def test_demoted_after_three_days_and_retried_after_seven(self):
        log = issues.empty()
        for d in ("2026-11-01", "2026-11-02"):
            issues.update_engines(log, [fail("urllib")], d)
        self.assertEqual(issues.demoted(log, dt.date(2026, 11, 2)), {})
        issues.update_engines(log, [fail("urllib")], "2026-11-03")
        self.assertEqual(issues.demoted(log, dt.date(2026, 11, 4)), {"site.example": {"urllib"}})
        self.assertEqual(issues.demoted(log, dt.date(2026, 11, 10)), {})   # day 7: tried first again
        issues.update_engines(log, [fail("urllib")], "2026-11-10")         # still refused → demoted anew
        self.assertEqual(issues.demoted(log, dt.date(2026, 11, 11)), {"site.example": {"urllib"}})

    def test_same_day_counts_once_and_success_resets(self):
        log = issues.empty()
        for _ in range(3):
            issues.update_engines(log, [fail("urllib")], "2026-11-01")
        self.assertEqual(log["engines"]["site.example"]["urllib"]["streak"], 1)
        issues.update_engines(log, [fail("urllib"), {**fail("urllib"), "ok": True}], "2026-11-02")
        self.assertEqual(log["engines"]["site.example"]["urllib"]["streak"], 0)
        self.assertEqual(issues.site_issues(log), [])


class _Eng:
    def __init__(self, via, ok):
        self.via, self.ok, self.calls = via, ok, 0

    def get(self, url):
        self.calls += 1
        if self.ok:
            return FetchResult(url=url, status=200, text="x", via=self.via)
        return FetchResult(url=url, status=403, blocked=True, blocked_reason="HTTP 403", via=self.via)


class Chain(unittest.TestCase):
    def test_demoted_engine_goes_last_on_that_site_only(self):
        u, p = _Eng("urllib", False), _Eng("playwright", True)
        ch = ChainFetcher([u, p], names=["urllib", "playwright"], demote={"site.example": {"urllib"}})
        r = ch.get("https://site.example/a")
        self.assertEqual((r.via, u.calls), ("playwright", 0))
        self.assertTrue(any("tried last" in n for n in r.notes))
        ch.get("https://other.example/a")
        self.assertEqual(u.calls, 1)
        self.assertEqual([(a["host"], a["via"], a["ok"]) for a in ch.attempts],
                         [("site.example", "playwright", True), ("other.example", "urllib", False),
                          ("other.example", "playwright", True)])

    def test_sole_engine_still_runs(self):
        u = _Eng("urllib", False)
        r = ChainFetcher([u], names=["urllib"], demote={"site.example": {"urllib"}}).get("https://site.example/")
        self.assertEqual((u.calls, r.blocked), (1, True))

    def test_run_records_engine_attempts(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ch = ChainFetcher([_Eng("urllib", False)], names=["urllib"])
        with mock.patch.object(runner, "adapter_for", adapter([V1], fail="blocked_403")):
            runner.run(Path(tmp.name), [act()], ch, TODAY, scan_gazette=False)
        log = issues.load(Path(tmp.name))
        self.assertEqual(log["engines"]["official.example"]["urllib"]["streak"], 1)


if __name__ == "__main__":
    unittest.main()
