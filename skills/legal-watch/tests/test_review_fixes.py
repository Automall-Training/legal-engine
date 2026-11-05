"""Regression tests for the review of step 9: each class reproduces one reported scenario."""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))
import legal_watch as cli  # noqa: E402
from test_runner import URL, V1, V2, Pages, act, adapter  # noqa: E402
from watch import clauses, digest, library as lib, manual, runner  # noqa: E402
from watch.contract import Redaction, classify  # noqa: E402

NOW = dt.datetime.now().astimezone()
TODAY = NOW.date()
QUOTE = "Forma consolidată valabilă la data de 01.10.2026"


def live_card(root: Path, act_id: str, *, latest=("v2", "2026-10-01"), archived=False, held=None) -> Path:
    """A `scope: "text"` version card that the real legal-research checker accepts."""
    (root / "sources").mkdir(parents=True, exist_ok=True)
    (root / "sources" / "act.txt").write_text(f"Text of the act. {QUOTE}. End.", encoding="utf-8")
    ev = {"url": URL, "opened_at": NOW.isoformat(timespec="seconds"), "official": True, "quote": QUOTE,
          "text_file": "sources/act.txt", "archived_on": TODAY.isoformat() if archived else None}
    points = {n: {"status": "done", "note": "read", "evidence": [dict(ev)]}
              for n in ("consolidation", "amendments", "deferred_entry", "repeal", "status_of_changes")}
    for n in ("secondary_acts", "case_law"):
        points[n] = {"status": "not_verified", "evidence": [], "reason": "not needed", "depends": "nothing"}
    held = held or {"label": latest[0], "version_from": latest[1]}
    card = {"schema_version": 1, "act": {"id": act_id, "title": "A", "jurisdiction": "RO", "official_record_url": URL},
            "checked_at": NOW.isoformat(timespec="seconds"), "analysis_date": TODAY.isoformat(), "scope": "text",
            "held_version": {**held, "snapshot_date": None, "sha256": None}, "cited_provisions": ["whole act"],
            "points": points, "latest_in_force": {"label": latest[0], "version_from": latest[1]},
            "next_versions": [], "changes": [], "related": [], "repealed": {"by": None, "from": None},
            "result": "current" if held["version_from"] == latest[1] else "outdated",
            "outdated_reason": None if held["version_from"] == latest[1] else "newer version in force",
            "working_conclusion": None}
    path = root / "card.json"
    path.write_text(json.dumps(card), encoding="utf-8")
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.profile = Path(self.tmp.name) / "profile"
        self.matter = Path(self.tmp.name) / "matter"

    def tearDown(self):
        self.tmp.cleanup()

    def run_with(self, acts, fake, today=TODAY, **kw):
        with mock.patch.object(runner, "adapter_for", fake):
            return runner.run(self.profile, acts, Pages(), today, scan_gazette=False, **kw)

    def index(self, act_id="ro.lege.1-2020"):
        clauses.save(self.profile, {"schema_version": 1, "contract": "c.docx", "jurisdiction": "RO",
                                    "indexed_on": "2026-11-01", "clauses": [
                                        {"clause": "7.1", "topic": "t", "acts": [{"id": act_id, "provision": None}],
                                         "source": "inferred", "needs_reverify": False, "reverify": []}]})


class HandCheckNeedsClosedLivePoints(Base):
    """Finding 1: an `outdated` card with open points or archive-only evidence must change nothing."""

    def test_real_card_through_real_checker_is_recorded(self):
        card = live_card(self.matter, "ro.lege.1-2020")
        out = manual.record(self.profile, [act()], card, TODAY, root=self.matter)
        r = out["acts"][0]
        self.assertEqual((r["status"], r["checked"], r["evidence"]["via"]), ("baseline", True, "host"))
        self.assertTrue(list((self.profile / "laws" / "texts" / "ro.lege.1-2020").glob("*.txt")))

    def test_archive_only_card_is_refused(self):
        card = live_card(self.matter, "ro.lege.1-2020", held={"label": "v1", "version_from": "2026-01-01"},
                         archived=True)
        with self.assertRaises(lib.WatchError):
            manual.record(self.profile, [act(current={"label": "v1", "in_force_from": "2026-01-01"})],
                          card, TODAY, root=self.matter)
        self.assertFalse((self.profile / "laws" / "state.json").exists())

    def test_card_about_another_date_or_part_is_refused(self):
        """Codex round 2: a card analysing an earlier date, or some articles, must not mark the act checked."""
        for change in ({"analysis_date": "2026-01-01"}, {"cited_provisions": ["art. 5"]}):
            card = live_card(self.matter, "ro.lege.1-2020")
            data = json.loads(card.read_text(encoding="utf-8"))
            data.update(change)
            card.write_text(json.dumps(data), encoding="utf-8")
            with self.subTest(change=change), self.assertRaises(lib.WatchError):
                manual.record(self.profile, [act()], card, TODAY, root=self.matter)

    def test_open_points_refused(self):
        card = {"points": {"consolidation": {"status": "not_verified", "evidence": []}}}
        self.assertEqual(manual.open_points(card)[0], "consolidation")


class HostOnlyReadsNothing(Base):
    """Finding 2: without the urllib engine, the EUR-Lex adapter must not fall back to Cellar over HTTP."""

    def test_no_cellar_without_urllib(self):
        eu = act("eu.reg.2016-679", sources=[{"kind": "eurlex", "celex": "32016R0679"}])
        with mock.patch("watch.adapters.cellar.urllib_get", side_effect=AssertionError("network")) as get:
            out = runner.run(self.profile, [eu], cli.HostOnly(), TODAY, direct_http=False)
        get.assert_not_called()
        self.assertEqual(out["acts"][0]["reasons"], ["host_only"])

    def test_cellar_getter_is_paced(self):
        g = runner.PacedCellarGet(pause_range=(1, 1), sleep=lambda s: calls.append(s))
        calls: list = []
        with mock.patch("watch.adapters.cellar.urllib_get", return_value=(200, "u", "x")):
            g("u1", {})
            g("u2", {})
        self.assertEqual(calls, [1])


class RepealIsReportedOnce(Base):
    """Finding 3: a repeal already held is not a new change and does not re-flag cleared clauses."""

    def test_second_run_is_known_repeal(self):
        self.index()
        held = {"current": {"label": "v1", "in_force_from": "2026-01-01"}}
        self.run_with([act(**held)], adapter([], repealed=True))
        clauses.clear(self.profile, "c.docx", None, "m-1")
        acts = lib.resolve_acts(lib.validate_watchlist({"acts": [{"id": "ro.lege.1-2020", "title": "A",
                                                                   "jurisdiction": "RO", "priority": "p1"}]}),
                                {}, lib.load_state(self.profile))
        out = self.run_with(acts, adapter([], repealed=True), today=TODAY + dt.timedelta(days=7))
        self.assertEqual((out["acts"][0]["status"], out["result"]), ("repealed_known", "OK"))
        self.assertEqual(clauses.pending(self.profile), [])


class VersionRules(unittest.TestCase):
    """Findings 4 and 5: never confirm a version the page does not show; a label alone is no change."""

    def test_postponed_next_is_not_verified(self):
        a = {"current": {"label": "v1", "in_force_from": "2026-01-01"},
             "next": {"label": "v2", "in_force_from": "2026-12-01"}}
        st, *_ = classify(act=a, parsed=[V1, Redaction("v2", "2027-06-01")], today=dt.date(2026, 12, 5),
                          repealed=False)
        self.assertEqual(st, "parse_failed")

    def test_same_date_other_label_is_unchanged(self):
        a = {"current": {"label": "LP189 din 10.07.25, MO502-505/25.09.25 art.652", "in_force_from": "2025-10-25"}}
        st, _, _, _, notes = classify(act=a, parsed=[Redaction("LP189/2025", "2025-10-25")],
                                      today=dt.date(2026, 1, 1), repealed=False)
        self.assertEqual(st, "unchanged")
        self.assertTrue(any("label differs" in n for n in notes))


class ClauseScanner(unittest.TestCase):
    """Findings 6, 7, 16: ids that match the catalog, Moldovan citations, real clause numbers, tables."""

    def ids(self, line, jur="RO"):
        catalog, _ = lib.load_catalog()
        return [i for i, _ in clauses.citations(line, jur, clauses.catalog_codes(catalog))]

    def test_eu_order_as_cited_matches_catalog(self):
        catalog, _ = lib.load_catalog()
        for line, want in (("Regulamentul (CE) nr. 593/2008", "eu.reg.593-2008"),
                           ("Directiva 93/13/CEE", "eu.dir.93-13"),
                           ("Regulamentul (UE) 2016/679", "eu.reg.2016-679")):
            with self.subTest(line=line):
                self.assertEqual(self.ids(line), [want])
                self.assertIn(want, catalog)

    def test_moldovan_style_and_codes(self):
        self.assertEqual(self.ids("Legea nr. 133 din 08.07.2011", "MD"), ["md.lege.133-2011"])
        self.assertEqual(self.ids("aprobat prin Legea nr. 1125-XV din 13 iunie 2002", "MD"), ["md.lege.1125-2002"])
        self.assertEqual(self.ids("Codul civil", "MD"), ["md.cod.civil"])
        self.assertEqual(self.ids("Legea nr. 287/2009 privind Codul civil"), ["ro.lege.287-2009"])
        self.assertEqual(self.ids("Codul muncii"), ["ro.lege.53-2003"])

    def test_numbers_that_are_not_clauses(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.txt"
            p.write_text("5.2. Plata se face\n30 de zile conform Codului civil\n", encoding="utf-8")
            ix = clauses.scan(p, "RO")
        self.assertEqual(ix["clauses"][0]["clause"], "5.2")

    def test_docx_tables_are_read(self):
        import docx
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "c.docx"
            d = docx.Document()
            d.add_table(rows=1, cols=1).cell(0, 0).text = "Conform Legii nr. 227/2015"
            d.save(p)
            ix = clauses.scan(p, "RO")
        self.assertEqual(ix["clauses"][0]["acts"][0]["id"], "ro.lege.227-2015")


class GazetteSignal(Base):
    """Finding 9: a Gazette item naming a watched act blocks "no changes" until it is answered."""

    SIG = {"act_id": "md.lege.1-2020", "edition_id": 9, "edition_number": "450", "edition_date": "2026-11-01",
           "item": "Lege pentru modificarea Legii nr. 1/2020", "matched": "1/2020", "url": "https://mo.example/9"}

    def scan(self, *a, **k):
        return mock.Mock(to_dict=lambda: {"source": "monitorul_md", "status": "complete", "checked_through": 9,
                                          "previous_checked_through": None, "latest_seen": 9, "editions": [],
                                          "signals": [self.SIG], "evidence": None, "error": None})

    def test_signal_keeps_the_act_unverified_until_answered(self):
        md = act("md.lege.1-2020", current={"label": "v1", "in_force_from": "2026-01-01"}, jurisdiction="MD")
        with mock.patch.object(runner, "adapter_for", adapter([V1])), \
                mock.patch.object(runner.monitorul_md, "scan", self.scan):
            out = runner.run(self.profile, [md], Pages(), TODAY)
        self.assertEqual((out["result"], out["acts"][0]["reasons"]), ("INCOMPLETE", ["gazette_signal"]))
        self.assertFalse(out["phrase_no_changes_allowed"])
        # The scan point moved on, but the signal is kept until the act is read anew.
        out = self.run_with([md], adapter([V1]), today=TODAY + dt.timedelta(days=7))
        self.assertEqual(out["acts"][0]["reasons"], ["gazette_signal"])
        out = self.run_with([md], adapter([V1, V2]), today=TODAY + dt.timedelta(days=14))
        self.assertTrue(out["acts"][0]["checked"])
        self.assertEqual(lib.load_state(self.profile)["signals"], {})

    def test_partial_run_scans_for_every_watched_act(self):
        """Codex review: a run of act A moved the scan point past an issue naming act B, losing B's signal."""
        a = act("md.lege.2-2020", current={"label": "v1", "in_force_from": "2026-01-01"}, jurisdiction="MD")
        b = act("md.lege.1-2020", current={"label": "v1", "in_force_from": "2026-01-01"}, jurisdiction="MD")
        seen = []
        def scan(acts, *rest):
            seen.append(sorted(x["id"] for x in acts))
            return self.scan()
        with mock.patch.object(runner, "adapter_for", adapter([V1])), \
                mock.patch.object(runner.monitorul_md, "scan", scan):
            runner.run(self.profile, [a, b], Pages(), TODAY, selector="md.lege.2-2020")
        self.assertEqual(seen, [["md.lege.1-2020", "md.lege.2-2020"]])
        self.assertIn("md.lege.1-2020", lib.load_state(self.profile)["signals"])
        out = self.run_with([a, b], adapter([V1]), today=TODAY + dt.timedelta(days=7))
        reasons = {r["act_id"]: r.get("reasons") for r in out["acts"]}
        self.assertEqual(reasons["md.lege.1-2020"], ["gazette_signal"])


class DayRuns(Base):
    """Findings 11, 13, 17: partial runs merge into the day, records do not count as complete runs."""

    def test_selector_run_merges_and_dry_run_is_apart(self):
        two = [act(), act("ro.lege.2-2020")]
        self.run_with(two, adapter([V1]))
        self.run_with(two, adapter([V1]), selector="ro.lege.2-2020")
        self.run_with(two, adapter([V1]), dry_run=True)
        day = json.loads((self.profile / "laws" / "runs" / TODAY.isoformat() / "run.json").read_text())
        self.assertEqual(len(day["acts"]), 2)
        self.assertTrue(day["full"])

    def test_record_alone_is_not_a_complete_run(self):
        manual.record(self.profile, [act()], live_card(self.matter, "ro.lege.1-2020"), TODAY, root=self.matter)
        h = digest.health(lib.load_state(self.profile), TODAY, "weekly")
        self.assertIsNone(h["last_complete"])
        self.assertFalse(h["overdue"])  # first run ever is never overdue

    def test_record_flags_only_its_own_act(self):
        self.index("ro.lege.2-2020")
        two = [act(current={"label": "v1", "in_force_from": "2026-01-01"}),
               act("ro.lege.2-2020", current={"label": "v1", "in_force_from": "2026-01-01"})]
        self.run_with(two, adapter([V1, V2]))
        clauses.clear(self.profile, "c.docx", None, "m-1")
        held = {"label": "v2", "version_from": "2026-10-01"}
        acts = [act(current={"label": "v2", "in_force_from": "2026-10-01"})]
        manual.record(self.profile, acts, live_card(self.matter, "ro.lege.1-2020", held=held), TODAY,
                      root=self.matter)
        self.assertEqual(clauses.pending(self.profile), [])

    def test_ok_with_p2_unverified_does_not_say_no_changes(self):
        out = self.run_with([act(current={"label": "v1", "in_force_from": "2026-01-01"}),
                             act("ro.lege.2-2020", p="p2")], adapter([V1]))
        self.assertEqual(out["result"], "OK")
        out2 = self.run_with([act(p="p2")], adapter([], fail="fetch_failed"), selector="ro.lege.1-2020")
        self.assertFalse(out2["phrase_no_changes_allowed"])
        self.assertIn("not verified", digest.render(out2, "en"))
        none = dict(out2, summary={**out2["summary"], "checked": 0})              # nothing was checked at all
        self.assertIn(digest.T["en"]["result"]["NONE"], digest.render(none, "en"))
        forbidden = {"en": "**no changes**", "ro": "**fără modificări**", "ru": "**без изменений**"}
        for lang, phrase in forbidden.items():
            text = digest.render(out2, lang)
            self.assertNotIn(phrase, text)
            self.assertNotIn(digest.T[lang]["nochanges"], text)


class CliErrors(unittest.TestCase):
    """Findings 12 and 15: a crash is never exit 1; unknown act ids are refused."""

    def call(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            return cli.main(list(argv)), err.getvalue()

    def test_crash_is_exit_3_and_missing_package_exit_2(self):
        with mock.patch.dict(cli.COMMANDS, {"show": mock.Mock(side_effect=KeyError("x"))}):
            self.assertEqual(self.call("--profile", "/tmp/x", "show")[0], 3)
        with mock.patch.dict(cli.COMMANDS, {"show": mock.Mock(side_effect=ImportError("no", name="playwright"))}):
            code, err = self.call("--profile", "/tmp/x", "show")
        self.assertEqual(code, 2)
        self.assertIn("WITH_PLAYWRIGHT", err)

    def test_unknown_act_id_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, niches = lib.load_catalog()
            code, err = self.call("--profile", tmp, "init", "--niches", next(iter(niches["niches"])),
                                  "--acts", "ro.lege.999-1999")
        self.assertEqual(code, 2)
        self.assertIn("not in the catalog", err)


if __name__ == "__main__":
    unittest.main()
