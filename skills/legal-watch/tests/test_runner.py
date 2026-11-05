"""Runner, state, snapshots, digest, contract flags and the host engine, with fake adapters (no network)."""

from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))
from watch import clauses, digest, library as lib, manual, runner  # noqa: E402
from watch.contract import AdapterResult, Evidence, Redaction, classify  # noqa: E402
from watch.fetchers import FetchResult  # noqa: E402

TODAY = dt.date(2026, 11, 4)
URL = "https://official.example/act"
TEXT = "Official text of the act. " * 50


class Pages:
    def __init__(self):
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        return FetchResult(url=url, status=200, text=TEXT, fetched_at="2026-11-04T07:00:00Z", via="urllib")


def adapter(parsed, *, calibrated=True, repealed=False, fail=None, crash=False):
    """A fake adapter that reads `parsed` versions from the page and classifies them like a real one."""
    def fn(act, fetcher, today):
        if crash:
            raise RuntimeError("boom")
        page = fetcher.get(URL)
        ev = Evidence(url=URL, fetched_at=page.fetched_at, sha256="a" * 64, parser="fake",
                      parser_calibrated=calibrated, via=page.via)
        if fail:
            return AdapterResult(act_id=act["id"], adapter="fake", status=fail, evidence=ev, error="site down")
        st, cur, nxt, err, notes = classify(act=act, parsed=parsed, today=today, repealed=repealed)
        return AdapterResult(act_id=act["id"], adapter="fake", status=st, current=cur, next=nxt, evidence=ev,
                             error=err, notes=notes)
    return lambda act: ("fake", fn)


def act(i="ro.lege.1-2020", p="p1", **kw):
    return {"id": i, "title": f"Act {i}", "jurisdiction": "RO", "priority": p, "current": None, "next": None, **kw}


V1 = Redaction(label="v1", in_force_from="2026-01-01")
V2 = Redaction(label="v2", in_force_from="2026-10-01")
FUT = Redaction(label="v3", in_force_from="2027-01-01")


class RunnerBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.profile = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_with(self, acts, fake, **kw):
        with mock.patch.object(runner, "adapter_for", fake):
            return runner.run(self.profile, acts, Pages(), TODAY, scan_gazette=False, **kw)

    def held(self, act_id="ro.lege.1-2020"):
        return lib.load_state(self.profile)["acts"].get(act_id)


class FirstReading(RunnerBase):
    def test_first_reading_is_a_baseline_not_a_change(self):
        out = self.run_with([act()], adapter([V1]))
        self.assertEqual(out["acts"][0]["status"], "baseline")
        self.assertTrue(out["acts"][0]["checked"])
        self.assertEqual(out["result"], "OK")
        self.assertEqual(out["changes"], [])
        self.assertEqual(self.held()["current"]["label"], "v1")

    def test_snapshot_saved_once_per_distinct_text(self):
        self.run_with([act()], adapter([V1]))
        held = self.held()
        self.run_with([act(current=held["current"])], adapter([V1]))
        files = list((self.profile / "laws" / "texts" / "ro.lege.1-2020").glob("*.txt"))
        self.assertEqual(len(files), 1)
        self.assertIn("Official text", files[0].read_text())

    def test_uncalibrated_baseline_is_not_accepted(self):
        out = self.run_with([act()], adapter([V1], calibrated=False))
        r = out["acts"][0]
        self.assertEqual((r["status"], r["adapter_status"]), ("parse_failed", "new_in_force"))  # what the adapter said
        self.assertEqual(out["result"], "INCOMPLETE")
        self.assertIsNone(self.held())


class Changes(RunnerBase):
    def test_unchanged_is_ok_and_allows_the_phrase(self):
        out = self.run_with([act(current={"label": "v1", "in_force_from": "2026-01-01"})], adapter([V1]))
        self.assertEqual((out["acts"][0]["status"], out["result"], out["exit_code"]), ("unchanged", "OK", 0))
        self.assertTrue(out["phrase_no_changes_allowed"])

    def test_new_version_in_force_moves_the_baseline(self):
        out = self.run_with([act(current={"label": "v1", "in_force_from": "2026-01-01"})], adapter([V1, V2]))
        self.assertEqual((out["result"], out["exit_code"]), ("CHANGES", 1))
        self.assertEqual(out["changes"][0]["kind"], "in_force")
        self.assertTrue(out["changes"][0]["confirmed"])
        self.assertEqual(self.held()["current"]["label"], "v2")

    def test_future_version_is_never_in_force(self):
        out = self.run_with([act(current={"label": "v1", "in_force_from": "2026-01-01"})], adapter([V1, FUT]))
        self.assertEqual(out["changes"][0]["kind"], "future")
        self.assertEqual(self.held()["current"]["label"], "v1")
        self.assertEqual(self.held()["next"]["label"], "v3")

    def test_uncalibrated_change_is_possible_and_keeps_the_baseline(self):
        out = self.run_with([act(current={"label": "v1", "in_force_from": "2026-01-01"})],
                            adapter([V1, V2], calibrated=False))
        self.assertFalse(out["changes"][0]["confirmed"])
        self.assertEqual(out["result"], "INCOMPLETE")
        self.assertIsNone(self.held())  # nothing held before, nothing written from an unconfirmed reading

    def test_repeal(self):
        out = self.run_with([act(current={"label": "v1", "in_force_from": "2026-01-01"})], adapter([], repealed=True))
        self.assertEqual(out["changes"][0]["kind"], "repealed")
        self.assertIn("repealed", self.held())


class Failures(RunnerBase):
    def test_failure_is_never_no_changes(self):
        out = self.run_with([act()], adapter([], fail="fetch_failed"))
        self.assertEqual((out["result"], out["exit_code"]), ("INCOMPLETE", 2))
        self.assertFalse(out["phrase_no_changes_allowed"])
        text = (self.profile / "laws" / "runs" / "2026-11-04" / "digest.md").read_text()
        self.assertNotIn("no changes", text.lower().split("**")[1])

    def test_p2_failure_does_not_block_ok(self):
        out = self.run_with([act(p="p2")], adapter([], fail="blocked_403"))
        self.assertEqual(out["result"], "OK")
        self.assertEqual(out["summary"]["unverified"], 1)

    def test_crashing_adapter_is_not_verified(self):
        out = self.run_with([act()], adapter([], crash=True))
        self.assertEqual(out["acts"][0]["reasons"], ["adapter_crashed"])

    def test_act_without_source(self):
        with mock.patch.object(runner, "adapter_for", lambda a: (None, None)):
            out = runner.run(self.profile, [act()], Pages(), TODAY, scan_gazette=False)
        self.assertEqual(out["acts"][0]["reasons"], ["no_source"])

    def test_dry_run_writes_no_state(self):
        self.run_with([act()], adapter([V1]), dry_run=True)
        self.assertFalse((self.profile / "laws" / "state.json").exists())
        self.assertTrue((self.profile / "laws" / "runs" / "2026-11-04" / "dry-run" / "run.json").exists())
        self.assertFalse((self.profile / "laws" / "runs" / "2026-11-04" / "run.json").exists())


class ContractFlags(RunnerBase):
    def write_index(self):
        ix = {"schema_version": 1, "contract": "services.docx", "jurisdiction": "RO", "indexed_on": "2026-11-01",
              "clauses": [{"clause": "5.2", "topic": "withdrawal", "acts": [{"id": "ro.lege.1-2020", "provision": None}],
                           "source": "inferred", "needs_reverify": False, "reverify": []},
                          {"clause": "9", "topic": "law", "acts": [{"id": "ro.lege.9-2009", "provision": None}],
                           "source": "cited", "needs_reverify": False, "reverify": []}]}
        clauses.save(self.profile, ix)

    def test_confirmed_change_flags_dependent_clauses_only(self):
        self.write_index()
        out = self.run_with([act(current={"label": "v1", "in_force_from": "2026-01-01"})], adapter([V1, V2]))
        self.assertEqual(out["contracts_to_review"], [{"contract": "services.docx", "index": "services.json",
                                                       "clauses": ["5.2"]}])
        pend = clauses.pending(self.profile)
        self.assertEqual([c["clause"] for c in pend[0]["clauses"]], ["5.2"])
        digest_text = (self.profile / "laws" / "runs" / "2026-11-04" / "digest.md").read_text()
        self.assertIn("services.docx", digest_text)

    def test_flag_is_idempotent_and_cleared_only_with_a_matter(self):
        self.write_index()
        for _ in range(2):
            self.run_with([act(current={"label": "v1", "in_force_from": "2026-01-01"})], adapter([V1, V2]))
        self.assertEqual(len(clauses.pending(self.profile)[0]["clauses"][0]["reverify"]), 1)
        with self.assertRaises(lib.WatchError):
            clauses.clear(self.profile, "services.docx", None, "")
        self.assertEqual(clauses.clear(self.profile, "services.docx", "5.2", "2026-11-04-reverify"), 1)
        self.assertEqual(clauses.pending(self.profile), [])
        with self.assertRaises(lib.WatchError):
            clauses.clear(self.profile, "services.docx", "5.2", "x")

    def test_unconfirmed_change_flags_nothing(self):
        self.write_index()
        out = self.run_with([act(current={"label": "v1", "in_force_from": "2026-01-01"})],
                            adapter([V1, V2], calibrated=False))
        self.assertEqual(out["contracts_to_review"], [])


class Digest(unittest.TestCase):
    RUN = {"date": "2026-11-04", "result": "INCOMPLETE",
           "summary": {"acts": 2, "checked": 1}, "changes": [
               {"act_id": "ro.lege.1-2020", "title": "A", "priority": "p1", "kind": "future", "label": "v3",
                "in_force_from": "2027-01-01", "confirmed": True}],
           "unverified": [{"act_id": "md.cod.civil", "title": "C", "priority": "p1", "reasons": ["blocked_403"]}],
           "contracts_to_review": [], "acts": [], "monitorul": {"signals": [
               {"act_id": "md.cod.civil", "edition_id": 9, "edition_number": "450", "edition_date": "2026-11-01",
                "item": "Lege pentru modificarea Codului civil", "url": "https://monitorul.example/9"}]},
           "health": {"last_complete": None, "overdue": True, "days_since": None}}

    def test_three_languages(self):
        for lang, word in (("ru", "Не проверено"), ("ro", "Neverificate"), ("en", "Not verified")):
            with self.subTest(lang=lang):
                text = digest.render(self.RUN, lang)
                self.assertIn(word, text)
                self.assertIn("2027-01-01", text)
                self.assertIn("monitorul.example/9", text)

    def test_unknown_language_falls_back_to_english(self):
        self.assertIn("Law monitoring", digest.render(self.RUN, "xx"))

    def test_health_overdue_after_nine_days(self):
        state = {"runs": [{"date": "2026-10-20", "result": "OK"}, {"date": "2026-11-03", "result": "INCOMPLETE"}]}
        h = digest.health(state, TODAY, "weekly")
        self.assertEqual((h["last_complete"], h["days_since"], h["overdue"]), ("2026-10-20", 15, True))
        self.assertFalse(digest.health(state, TODAY, "on-request")["overdue"])


def card(act_id="ro.lege.1-2020", *, result="current", latest=("v2", "2026-10-01"), nxt=None, sha="b" * 64,
         repealed=None):
    return {"act": {"id": act_id, "title": "A"}, "result": result,
            "latest_in_force": {"label": latest[0], "version_from": latest[1]},
            "next_versions": [{"label": nxt[0], "applies_from": nxt[1]}] if nxt else [],
            "repealed": repealed or {"by": None, "from": None},
            "points": {"consolidation": {"status": "done", "evidence": [{"url": URL, "text_sha256": sha}]},
                       **{n: {"status": "done", "evidence": [{"url": URL}]}
                          for n in ("amendments", "deferred_entry", "repeal", "status_of_changes")}},
            "checked_at": "2026-11-04T10:00:00+02:00", "analysis_date": "2026-11-04", "scope": "text",
            "cited_provisions": ["whole act"]}


class HostEngine(RunnerBase):
    def test_card_equal_to_baseline_is_unchanged(self):
        res = manual.card_to_result(act(current={"label": "v2", "in_force_from": "2026-10-01"}), card(), TODAY, "text read")
        self.assertEqual((res.status, res.adapter, res.evidence.via), ("unchanged", "host", "host"))

    def test_card_with_newer_version_is_a_change(self):
        res = manual.card_to_result(act(current={"label": "v1", "in_force_from": "2026-01-01"}), card(), TODAY)
        self.assertEqual(res.status, "new_in_force")

    def test_card_future_repeal_is_next(self):
        res = manual.card_to_result(act(current={"label": "v2", "in_force_from": "2026-10-01"}),
                                    card(repealed={"by": "Law X", "from": "2027-03-01"}), TODAY)
        self.assertEqual((res.status, res.next.in_force_from), ("new_future", "2027-03-01"))

    def test_card_repealed_today(self):
        res = manual.card_to_result(act(), card(repealed={"by": "Law X", "from": "2026-11-01"}), TODAY)
        self.assertEqual(res.status, "repealed")

    def test_card_without_hash_cannot_be_unchanged(self):
        res = manual.card_to_result(act(current={"label": "v2", "in_force_from": "2026-10-01"}), card(), TODAY)
        self.assertEqual(res.status, "parse_failed")

    def test_refusals(self):
        with self.assertRaises(lib.WatchError):
            manual.card_to_result(act(), card(act_id="ro.lege.2-2020"), TODAY)
        with self.assertRaises(lib.WatchError):
            manual.card_to_result(act(), card(result="not_verified"), TODAY)

    def test_record_merges_into_todays_run(self):
        self.run_with([act(), act("ro.lege.2-2020", p="p2")], adapter([], fail="blocked_403"))
        fake_checker = mock.Mock()
        fake_checker.load.return_value = card()
        fake_checker.validate.return_value = {"errors": []}
        with mock.patch.object(manual, "_checker", return_value=fake_checker):
            out = manual.record(self.profile, [act(), act("ro.lege.2-2020", p="p2")], Path("card.json"), TODAY)
        rec = {r["act_id"]: r for r in out["acts"]}
        self.assertEqual(rec["ro.lege.1-2020"]["status"], "baseline")
        self.assertTrue(rec["ro.lege.1-2020"]["checked"])
        self.assertEqual(len(out["acts"]), 2)
        self.assertEqual(out["result"], "OK")  # the p1 act is now checked; the p2 failure does not block
        self.assertEqual(self.held()["via"], "host")

    def test_record_refuses_a_failing_card(self):
        fake_checker = mock.Mock()
        fake_checker.load.return_value = card()
        fake_checker.validate.return_value = {"errors": ["card is not from today: re-check required"]}
        with mock.patch.object(manual, "_checker", return_value=fake_checker), self.assertRaises(lib.WatchError):
            manual.record(self.profile, [act()], Path("card.json"), TODAY)

    def test_real_checker_is_found(self):
        self.assertTrue(hasattr(manual._checker(), "validate"))


class State(RunnerBase):
    def test_state_schema_and_history_cap(self):
        st = lib.load_state(self.profile)
        st["runs"] = [{"date": f"d{i}", "result": "OK"} for i in range(50)]
        lib.save_state(self.profile, st)
        self.assertEqual(len(lib.load_state(self.profile)["runs"]), lib.RUN_HISTORY)
        (self.profile / "laws" / "state.json").write_text(json.dumps({"schema_version": 9}))
        with self.assertRaises(lib.WatchError):
            lib.load_state(self.profile)


if __name__ == "__main__":
    unittest.main()
