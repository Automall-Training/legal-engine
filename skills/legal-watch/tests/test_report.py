"""The page for the person (laws/report.html) and the commands around the error log."""

from __future__ import annotations

import datetime as dt
import json
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cli import call  # noqa: E402
from test_runner import TODAY, V1, RunnerBase, act, adapter  # noqa: E402
from watch import digest, issues, library as lib, report  # noqa: E402
from watch.contract import AdapterResult, Evidence  # noqa: E402


def evil(act_, fetcher, today):
    page = fetcher.get("https://official.example/act")
    ev = Evidence(url="https://official.example/act?<b>x</b>", fetched_at=page.fetched_at, parser="fake",
                  parser_calibrated=True, via="urllib", http_status=403)
    return AdapterResult(act_id=act_["id"], adapter="fake", status="blocked_403", evidence=ev,
                         error='<script>alert("x")</script>')


class Page(RunnerBase):
    def test_written_after_a_run_with_open_problem_and_library(self):
        self.run_with([act(), act("ro.lege.2-2020", p="p2")], lambda a: ("fake", evil if a["id"] == "ro.lege.1-2020"
                                                                          else adapter([V1])(a)[1]))
        page = report.path(self.profile).read_text(encoding="utf-8")
        self.assertIn("ro.lege.1-2020", page)
        self.assertIn(digest.T["en"]["why"]["blocked_403"], page)
        self.assertIn("record a version card", page)          # what the agent will do
        self.assertIn("HTTP 403", page)
        self.assertIn("ro.lege.2-2020", page)                  # library section
        self.assertIn("v1", page)

    def test_everything_from_outside_is_escaped(self):
        self.run_with([act()], lambda a: ("fake", evil))
        page = report.path(self.profile).read_text(encoding="utf-8")
        self.assertNotIn("<script>", page)
        self.assertNotIn("<b>x</b>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_damaged_state_cannot_inject_attributes(self):
        self.run_with([act()], adapter([V1], fail="fetch_failed"))
        log = issues.load(self.profile)
        log["acts"]["ro.lege.1-2020"]["priority"] = "p1 onmouseover=alert(1)"
        issues.save(self.profile, log)
        page = report.render(self.profile, "en", TODAY)
        self.assertNotRegex(page, r"<tr[^>]*onmouseover")

    def test_repeal_is_shown_not_the_old_version_as_in_force(self):
        state = lib.load_state(self.profile)
        state["acts"]["ro.lege.1-2020"] = {"current": {"label": "v1", "in_force_from": "2026-01-01"}, "repealed": {"label": "repealed by Law X",
                                                                                 "in_force_from": "2026-10-01"},
                                           "checked_on": "2026-11-04"}
        lib.save_state(self.profile, state)
        page = report.render(self.profile, "en", TODAY)
        self.assertIn(digest.T["en"]["kind"]["repealed"] + ": repealed by Law X", page)

    def test_empty_profile_and_languages(self):
        for lang in ("en", "ro", "ru", "xx"):
            page = report.render(self.profile, lang, TODAY)
            self.assertIn("<html", page)
        self.assertIn(report.P["ru"]["none_open"], report.render(self.profile, "ru", TODAY))

    def test_solved_and_sites_sections(self):
        self.run_with([act()], adapter([V1], fail="fetch_failed"))
        self.run_with([act()], adapter([V1]))
        log = issues.load(self.profile)
        for d in ("2026-11-01", "2026-11-02", "2026-11-03"):
            issues.update_engines(log, [{"host": "site.example", "via": "urllib", "ok": False, "error": "HTTP 403"}], d)
        issues.save(self.profile, log)
        page = report.render(self.profile, "en", TODAY)
        self.assertIn(report.P["en"]["resolved"], page)
        self.assertIn("checked by a run", page)
        self.assertIn("site.example", page)
        self.assertIn(report.P["en"]["tried_last"], page)

    def test_dry_run_writes_no_page(self):
        self.run_with([act()], adapter([V1], fail="fetch_failed"), dry_run=True)
        self.assertFalse(report.path(self.profile).exists())

    def test_digest_points_to_the_page(self):
        out = self.run_with([act()], adapter([V1], fail="fetch_failed"))
        self.assertIn("laws/report.html", digest.render(out, "ru"))


class Commands(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.profile = Path(self.tmp.name)
        self.niche = next(iter(lib.load_catalog()[1]["niches"]))

    def p(self, *argv):
        return call("--profile", str(self.profile), *argv)

    def init(self):
        code, out, _ = self.p("init", "--niches", self.niche, "--acts", "none", "--add",
                              "eu.reg.2016-679,md.cod.civil", "--engines", "host")
        self.assertEqual(code, 0, out)

    def test_issues_and_report(self):
        self.init()
        log = issues.empty()
        issues.update_acts(log, [{"act_id": "md.cod.civil", "reasons": ["no_source"], "priority": "p1"}], set(),
                           "2026-11-04", "t")
        issues.save(self.profile, log)
        out = json.loads(self.p("issues")[1])
        self.assertEqual([i["act_id"] for i in out["open"]], ["md.cod.civil"])
        self.assertIn("engines", json.loads(self.p("issues", "--all")[1]))
        code, out, _ = self.p("report")
        self.assertEqual(code, 0)
        self.assertTrue(Path(out.strip()).is_file())

    def test_source_add(self):
        self.init()
        code, out, _ = self.p("source", "add", "md.cod.civil", "--doc-id", "12345")
        self.assertEqual(code, 0, out)
        wl = lib.load_watchlist(self.profile / "laws" / "watchlist.yaml")
        entry = next(a for a in wl["acts"] if a["id"] == "md.cod.civil")
        self.assertEqual(entry["sources"], [{"kind": "legis_md", "doc_id": "12345"}])
        self.p("source", "add", "md.cod.civil", "--doc-id", "67890")   # replaced, not doubled
        wl = lib.load_watchlist(self.profile / "laws" / "watchlist.yaml")
        self.assertEqual(len(next(a for a in wl["acts"] if a["id"] == "md.cod.civil")["sources"]), 1)
        self.assertEqual(self.p("source", "add", "eu.reg.2016-679", "--doc-id", "1")[0], 2)   # EU needs celex
        self.assertEqual(self.p("source", "add", "ro.lege.nope-1", "--doc-id", "1")[0], 2)

    def test_show_gives_held_version_for_the_card(self):
        self.init()
        state = lib.load_state(self.profile)
        state["acts"]["md.cod.civil"] = {"current": {"label": "v1", "in_force_from": "2026-01-01"}}
        lib.save_state(self.profile, state)
        civil = next(a for a in json.loads(self.p("show")[1])["acts"] if a["id"] == "md.cod.civil")
        self.assertEqual(civil["held_version"], {"label": "v1", "version_from": "2026-01-01"})

    def test_show_lists_text_copies(self):
        self.init()
        lib.save_snapshot(self.profile, "md.cod.civil", "text", "c" * 64, "2026-11-04")
        show = json.loads(self.p("show")[1])
        civil = next(a for a in show["acts"] if a["id"] == "md.cod.civil")
        self.assertEqual(civil["texts"], ["texts/md.cod.civil/2026-11-04-cccccccccccc.txt"])

    def test_prune_lists_then_removes_old_runs_only(self):
        runs = self.profile / "laws" / "runs"
        old = (dt.date.today() - dt.timedelta(days=400)).isoformat()
        new = dt.date.today().isoformat()
        for d in (old, new):
            (runs / d).mkdir(parents=True)
        (runs / "schedule.log").write_text("x", encoding="utf-8")
        out = json.loads(self.p("prune", "--runs-older", "365")[1])
        self.assertEqual(out["would_remove"], [old])
        self.assertTrue((runs / old).exists())
        out = json.loads(self.p("prune", "--runs-older", "365", "--apply")[1])
        self.assertEqual(out["removed"], [old])
        self.assertFalse((runs / old).exists())
        self.assertTrue((runs / new).exists() and (runs / "schedule.log").exists())
        self.assertEqual(self.p("prune", "--runs-older", "5")[0], 2)


if __name__ == "__main__":
    unittest.main()
