"""legis_md adapter: saved page → status. No network.

HTML fixtures are synthetic (legis.md never served a live body to an automated browser); the markdown fixtures
`markdown-*.md` are live markdown pages of public acts (law text cut).
"""
import copy
import datetime as dt
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from watch.adapters import legis_md  # noqa: E402
from watch.contract import (BLOCKED_403, FETCH_FAILED, NEW_FUTURE, NEW_IN_FORCE, PARSE_FAILED,  # noqa: E402
                            REPEALED, STATUSES, UNCHANGED)
from watch.fetchers import FetchResult, FixtureFetcher, fixture_result  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
T = dt.date(2026, 9, 28)
T_MD = dt.date(2026, 10, 2)          # the day the markdown pages were captured
URL_CM = legis_md.PAGE_URL.format(doc_id="155185")


def read(rel: str) -> str:
    return (FIX / rel).read_text(encoding="utf-8")


def cm_act():
    return {"id": "md.cod.muncii", "title": "Codul muncii al Republicii Moldova", "jurisdiction": "MD",
            "number": "154", "year": "2003", "code": "muncii", "priority": "p1",
            "current": {"label": "LP114 din 18.06.26, MO288-290/30.06.26 art.290", "in_force_from": "2026-06-30"},
            "next": None, "sources": [{"kind": "legis_md", "doc_id": "155185"}]}


def run(act, html=None, *, status=200, result=None, today=T):
    _, url = legis_md.page_source(act)
    r = result if result is not None else fixture_result(url, html, status=status)
    return legis_md.check_act(act, FixtureFetcher({url: r}), today)


class HtmlPath(unittest.TestCase):
    def test_normal_page_unchanged(self):
        res = run(cm_act(), read("legis_md/normal.html"))
        self.assertEqual(res.status, UNCHANGED, res)
        self.assertEqual(res.current.label, "LP114 din 18.06.26, MO288-290/30.06.26 art.290")
        self.assertEqual(res.current.in_force_from, "2026-06-30")
        self.assertIsNone(res.next)
        self.assertIsNone(res.error)
        self.assertEqual(len(res.evidence.sha256), 64)
        self.assertTrue(res.evidence.parser.endswith("amendment-list"))
        self.assertEqual(res.evidence.via, "fixture")
        self.assertFalse(res.evidence.parser_calibrated)
        self.assertTrue(any("not calibrated" in n for n in res.notes))

    def test_inline_article_repeal_note_is_not_act_repeal(self):
        self.assertNotEqual(run(cm_act(), read("legis_md/normal.html")).status, REPEALED)

    def test_new_version_in_force(self):
        res = run(cm_act(), read("legis_md/new-in-force.html"))
        self.assertEqual(res.status, NEW_IN_FORCE)
        self.assertTrue(res.current.label.startswith("LP150"))
        self.assertEqual(res.current.in_force_from, "2026-09-15")

    def test_future_version_is_new_future_not_in_force(self):
        res = run(cm_act(), read("legis_md/new-future.html"))
        self.assertEqual(res.status, NEW_FUTURE)
        self.assertTrue(res.current.label.startswith("LP114"))
        self.assertTrue(res.next.label.startswith("LP170"))
        self.assertEqual(res.next.in_force_from, "2027-01-01")

    def test_future_already_known_is_unchanged(self):
        act = cm_act()
        act["next"] = {"label": "LP170 din 11.09.26, MO470/22.09.26 art.500", "in_force_from": "2027-01-01"}
        self.assertEqual(run(act, read("legis_md/new-future.html")).status, UNCHANGED)

    def test_future_becomes_in_force_on_its_date(self):
        res = run(cm_act(), read("legis_md/new-future.html"), today=dt.date(2027, 1, 1))
        self.assertEqual(res.status, NEW_IN_FORCE)
        self.assertEqual(res.current.in_force_from, "2027-01-01")

    def test_held_next_started_but_page_old_is_not_unchanged(self):
        # The next version lives under another doc_id; the old page never shows it.
        act = cm_act()
        act["next"] = {"label": "LP138 din 09.07.26, MO338/28.07.26 art.344", "in_force_from": "2026-10-28"}
        res = run(act, read("legis_md/normal.html"), today=dt.date(2026, 11, 2))
        self.assertEqual(res.status, NEW_IN_FORCE)
        self.assertEqual(res.current.in_force_from, "2026-10-28")
        self.assertTrue(any("held next version" in n for n in res.notes))

    def test_cloudflare_challenge_is_blocked(self):
        res = run(cm_act(), read("legis_md/cloudflare-challenge-2026-09-27.html"), status=403)
        self.assertEqual(res.status, BLOCKED_403)
        self.assertIn("not bypassed", res.error)

    def test_plain_403_is_blocked(self):
        res = run(cm_act(), "<html><head><title>Forbidden</title></head><body>403</body></html>", status=403)
        self.assertEqual(res.status, BLOCKED_403)

    def test_body_blocked_by_subresource_403(self):
        r = FetchResult(url=URL_CM, status=200, title="CM154/2003", html="<html></html>", text="CM154/2003",
                        fetched_at="2026-09-28T07:00:00Z", subresource_403=["https://www.legis.md/js/x.js"])
        self.assertEqual(run(cm_act(), result=r).status, BLOCKED_403)

    def test_empty_or_truncated_is_parse_failed(self):
        for name in ("truncated.html", "empty.html"):
            res = run(cm_act(), read(f"legis_md/{name}"))
            self.assertEqual(res.status, PARSE_FAILED, name)
            self.assertTrue(res.error)

    def test_amendments_without_start_date_are_parse_failed(self):
        self.assertEqual(run(cm_act(), read("legis_md/no-dates.html")).status, PARSE_FAILED)

    def test_wrong_act_page_is_parse_failed(self):
        res = run(cm_act(), read("legis_md/wrong-act.html"))
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertIn("does not identify", res.error)

    def test_act_without_number_year_is_parse_failed(self):
        act = cm_act()
        del act["number"], act["year"]
        res = run(act, read("legis_md/normal.html"))
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertIn("no number/year", res.error)

    def test_number_year_from_id_tail(self):
        act = cm_act()
        del act["number"], act["year"]
        act["id"] = "md.cod.muncii-154-2003"
        self.assertEqual(run(act, read("legis_md/normal.html")).status, UNCHANGED)

    def test_page_older_than_baseline_is_parse_failed(self):
        act = cm_act()
        act["current"] = {"label": "LP150 din 01.08.26, MO400-402/15.09.26 art.410", "in_force_from": "2026-09-15"}
        self.assertEqual(run(act, read("legis_md/normal.html")).status, PARSE_FAILED)

    def test_network_failure_is_fetch_failed(self):
        r = FetchResult(url=URL_CM, status=None, fetched_at="2026-09-28T07:00:00Z", via="urllib",
                        error="TimeoutError: timed out")
        res = run(cm_act(), result=r)
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertIn("Timeout", res.error)
        self.assertEqual(res.evidence.via, "urllib")

    def test_http_500_is_fetch_failed(self):
        self.assertEqual(run(cm_act(), "<html><body>err</body></html>", status=500).status, FETCH_FAILED)

    def test_missing_fixture_is_fetch_failed(self):
        self.assertEqual(legis_md.check_act(cm_act(), FixtureFetcher({}), T).status, FETCH_FAILED)

    def test_repealed_act(self):
        act = {"id": "md.lege.77-2016", "jurisdiction": "MD",
               "current": {"label": "LP125 din 30.05.24, MO236-237/31.05.24 art.338", "in_force_from": "2024-05-31"},
               "next": None, "sources": [{"kind": "legis_md", "doc_id": "143443"}]}
        res = run(act, read("legis_md/repealed.html"))
        self.assertEqual(res.status, REPEALED)
        self.assertIn("LP999", res.current.label)

    def test_base_form_unchanged(self):
        act = {"id": "md.lege.247-2024", "jurisdiction": "MD",
               "current": {"label": "forma de bază (aplicare după 12 luni)", "in_force_from": "2025-11-26"},
               "next": None, "sources": [{"kind": "legis_md", "doc_id": "145889"}]}
        res = run(act, read("legis_md/base-form.html"))
        self.assertEqual(res.status, UNCHANGED)
        self.assertTrue(res.evidence.parser.endswith("base-form"))

    def test_source_without_doc_id_is_fetch_failed(self):
        act = {"id": "md.lege.105-2003", "jurisdiction": "MD", "current": None, "next": None,
               "sources": [{"kind": "legis_md"}]}
        res = legis_md.check_act(act, FixtureFetcher({}), T)
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertIn("doc_id", res.error)

    def test_baseline_absent_is_never_unchanged(self):
        act = cm_act()
        act["current"] = None
        self.assertEqual(run(act, read("legis_md/normal.html")).status, NEW_IN_FORCE)

    def test_every_fixture_yields_known_status_and_serialises(self):
        for name in ["normal.html", "new-in-force.html", "new-future.html", "truncated.html", "empty.html",
                     "wrong-act.html", "no-dates.html", "cloudflare-challenge-2026-09-27.html"]:
            d = run(cm_act(), read(f"legis_md/{name}")).to_dict()
            self.assertIn(d["status"], STATUSES)
            self.assertEqual(d["act_id"], "md.cod.muncii")
            self.assertFalse(d["evidence"]["parser_calibrated"])
            if d["error"]:
                self.assertNotEqual(d["status"], UNCHANGED)


# ---------------------------------------------------------------- markdown path (live pages)

LIVE = {
    "155185": {"id": "md.cod.muncii", "number": "154", "year": "2003", "code": "muncii",
               "current": {"label": "LP114 din 18.06.26, MO288-290/30.06.26 art.290", "in_force_from": "2026-06-30"},
               "next": {"label": "LP138 din 09.07.26, MO338/28.07.26 art.344", "in_force_from": "2026-10-28"}},
    "150997": {"id": "md.lege.105-2003",
               "current": {"label": "republicată 28.03.2024 (MO 122-124 art. 195), mod. LP189 din 10.07.25",
                           "in_force_from": "2025-10-25"}, "next": None},
    "144681": {"id": "md.lege.195-2024",
               "current": {"label": "forma de bază + LP160 din 30.07.26 art. 45 alin. (2) (MO 382-385/20.08.26), "
                                    "în vigoare 23.08.2026", "in_force_from": "2026-08-23"}, "next": None},
}


def live_act(doc_id):
    a = copy.deepcopy(LIVE[doc_id])
    a.update(jurisdiction="MD", priority="p1", sources=[{"kind": "legis_md", "doc_id": doc_id}])
    return a


def md_page(doc_id, md=None, via="command"):
    url = legis_md.PAGE_URL.format(doc_id=doc_id)
    md = md if md is not None else read(f"legis_md/markdown-{doc_id}-2026-10-02.md")
    return url, fixture_result(url, "", via=via, markdown=md)


def run_md(act, doc_id, md=None, today=T_MD):
    url, r = md_page(doc_id, md)
    return legis_md.check_act(act, FixtureFetcher({url: r}), today)


class MarkdownPath(unittest.TestCase):
    def test_live_pages_calibrated_unchanged(self):
        for doc_id in LIVE:
            with self.subTest(doc_id=doc_id):
                a = live_act(doc_id)
                res = run_md(a, doc_id)
                self.assertEqual(res.status, UNCHANGED, (res.error, res.notes))
                self.assertTrue(res.evidence.parser_calibrated)
                self.assertTrue(res.evidence.parser.startswith(legis_md.PARSER_ID_MD))
                self.assertEqual(res.evidence.via, "command")
                self.assertEqual(res.current.in_force_from, a["current"]["in_force_from"])

    def test_future_version_never_current(self):
        a = live_act("155185")
        res = run_md(a, "155185")
        self.assertEqual(res.current.in_force_from, "2026-06-30")
        self.assertEqual(res.next.in_force_from, "2026-10-28")
        later = run_md(a, "155185", today=dt.date(2026, 10, 29))
        self.assertEqual(later.status, NEW_IN_FORCE)
        self.assertEqual(later.current.in_force_from, "2026-10-28")

    def test_new_amendment_detected(self):
        md = read("legis_md/markdown-150997-2026-10-02.md").replace(
            "| LP189 din 10.07.25,",
            "| LP77 din 10.09.26, MO400/20.09.26 art.1; în vigoare 01.10.26<br>LP189 din 10.07.25,", 1)
        res = run_md(live_act("150997"), "150997", md)
        self.assertEqual(res.status, NEW_IN_FORCE)
        self.assertTrue(res.current.label.startswith("LP77 din 10.09.26"))

    def test_repeal_in_act_card(self):
        md = read("legis_md/markdown-150997-2026-10-02.md").replace(
            "| Data abrogării | - |", "| Data abrogării | 01.09.2026 |", 1)
        self.assertEqual(run_md(live_act("150997"), "150997", md).status, REPEALED)

    def test_future_repeal_is_future_version(self):
        md = read("legis_md/markdown-150997-2026-10-02.md").replace(
            "| Data abrogării | - |", "| Data abrogării | 01.03.2027 |", 1)
        res = run_md(live_act("150997"), "150997", md)
        self.assertEqual(res.status, NEW_FUTURE)
        self.assertEqual(res.next.in_force_from, "2027-03-01")

    def test_loading_stub_is_parse_failed(self):
        res = run_md(live_act("150997"), "150997", "Conținutul se încarcă...")
        self.assertEqual(res.status, PARSE_FAILED)

    def test_wrong_act_markdown_is_parse_failed(self):
        res = run_md(live_act("150997"), "150997", read("legis_md/markdown-155185-2026-10-02.md"))
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertIn("does not identify", res.error)

    def test_html_path_stays_uncalibrated(self):
        a = live_act("150997")
        url = legis_md.PAGE_URL.format(doc_id="150997")
        page = fixture_result(url, "<html><title>LP105/2003</title><body>" + "x " * 1500
                              + "LP189 din 10.07.25, MO502-505/25.09.25 art.652; în vigoare 25.10.25</body></html>")
        res = legis_md.check_act(a, FixtureFetcher({url: page}), T_MD)
        self.assertFalse(res.evidence.parser_calibrated)


L160 = "155902"


def l160_act(label="text inițial, MO 382-385/20.08.2026"):
    return {"id": "md.lege.160-2026", "jurisdiction": "MD", "next": None,
            "current": {"label": label, "in_force_from": "2026-08-23"},
            "sources": [{"kind": "legis_md", "doc_id": L160}]}


class AlignWithBaseline(unittest.TestCase):
    def test_base_form_same_date_is_unchanged(self):
        res = run_md(l160_act(), L160)
        self.assertEqual(res.status, UNCHANGED, (res.error, res.notes))
        self.assertEqual(res.current.in_force_from, "2026-08-23")
        self.assertTrue(res.evidence.parser_calibrated)
        self.assertTrue(any("same start date 2026-08-23" in n for n in res.notes))

    def test_same_date_other_amending_act_is_new(self):
        add = "| LP5 din 01.08.26, MO390/21.08.26 art.1; în vigoare 23.08.26 |\n"
        md = add + read(f"legis_md/markdown-{L160}-2026-10-02.md")
        res = run_md(l160_act(), L160, md)
        self.assertEqual(res.status, NEW_IN_FORCE)
        self.assertTrue(res.current.label.startswith("LP5 din 01.08.26"))
        # The baseline names the amending act's Official Gazette number → the same version.
        res2 = run_md(l160_act("Legea nr. 5/2026, MO 390/21.08.2026"), L160, md)
        self.assertEqual(res2.status, UNCHANGED, (res2.error, res2.notes))

    def test_new_bar_date_is_new_in_force(self):
        md = read(f"legis_md/markdown-{L160}-2026-10-02.md").replace(
            "- [23-08-2026]", "- [01-10-2026](https://www.legis.md/x)\n- [23-08-2026]", 1)
        res = run_md(l160_act(), L160, md)
        self.assertEqual(res.status, NEW_IN_FORCE)
        self.assertEqual(res.current.in_force_from, "2026-10-01")

    def test_baseline_doc_id_kept_when_present(self):
        a = l160_act()
        a["current"]["doc_id"] = "999"
        self.assertIs(legis_md.with_page_doc_id(a, L160), a)
        self.assertIs(legis_md.with_page_doc_id({"current": None}, L160)["current"], None)

    def test_unreadable_amending_label_is_not_aligned(self):
        from watch.contract import Redaction
        reds = [Redaction(label="XX1 din 01.08.26, MO390/21.08.26 art.1", in_force_from="2026-08-23")]
        # AMENDMENT_RE matches but ACT_TOKEN_RE also matches: aligned only via the MO number.
        notes = legis_md.align_with_baseline(l160_act("other text"), reds, L160)
        self.assertEqual(notes, [])
        self.assertIsNone(reds[0].doc_id)
        self.assertEqual(legis_md.align_with_baseline({"current": None}, reds, L160), [])


if __name__ == "__main__":
    unittest.main()
