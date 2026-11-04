"""just_ro adapter: saved page → status. No network.

Live excerpts are Wayback `id_` copies (the portal's bytes): oug34-consolidated, oug18-base, og21-republished,
oug141-base, codfiscal-171282, codulmuncii-41627. The other fixtures are synthetic (marked in their first line).
"""
import datetime as dt
import re
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from watch.adapters import just_ro  # noqa: E402
from watch.adapters.common import md_to_text  # noqa: E402
from watch.contract import (BLOCKED_403, FETCH_FAILED, NEW_FUTURE, NEW_IN_FORCE, PARSE_FAILED,  # noqa: E402
                            REPEALED, STATUSES, UNCHANGED)
from watch.fetchers import FetchResult, FixtureFetcher, fixture_result  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
T = dt.date(2026, 9, 28)


def read(rel: str) -> str:
    return (FIX / rel).read_text(encoding="utf-8")


def act(aid="ro.oug.34-2014", doc_id="158913", label="consolidare 20.07.2022", date="2022-07-20", nxt=None,
        code=None, number=None, year=None):
    a = {"id": aid, "jurisdiction": "RO", "priority": "p1",
         "current": {"label": label, "in_force_from": date} if label else None, "next": nxt,
         "sources": [{"kind": "just_ro", "doc_id": doc_id}]}
    if code:
        a["code"] = code
    if number:
        a["number"], a["year"] = number, year
    return a


OUG18 = dict(aid="ro.oug.18-2026", doc_id="308474", label="aplicare de la 19.06.2026", date="2026-06-19")
CF = dict(aid="ro.cod.fiscal", doc_id="171282", label="consolidare 01.01.2026", date="2026-01-01",
          code="fiscal", number="227", year="2015")
CM = dict(aid="ro.cod.muncii", doc_id="41627", label="consolidare 18.12.2025", date="2025-12-18",
          code="muncii", number="53", year="2003")
CF_HTML, CM_HTML = "just_ro/codfiscal-171282-wb20251231.html", "just_ro/codulmuncii-41627-wb20260215.html"
OUG34 = "just_ro/oug34-consolidated-wb20251217.html"


def run(a, html=None, *, status=200, result=None, today=T):
    _, url = just_ro.page_source(a)
    r = result if result is not None else fixture_result(url, html, status=status)
    return just_ro.check_act(a, FixtureFetcher({url: r}), today)


class LiveExcerpts(unittest.TestCase):
    def test_consolidated_page_unchanged(self):
        res = run(act(), read(OUG34))
        self.assertEqual(res.status, UNCHANGED, res)
        self.assertEqual(res.current.label, "consolidare 20.07.2022")
        self.assertEqual(res.current.doc_id, "158913")
        self.assertTrue(res.evidence.parser.endswith("consolidations"))
        self.assertEqual(len(res.evidence.sha256), 64)
        self.assertFalse(res.evidence.parser_calibrated)
        self.assertEqual(res.evidence.via, "fixture")
        self.assertTrue(any("Wayback id_ copies" in n for n in res.notes))

    def test_republished_act_with_consolidations(self):
        res = run(act("ro.og.21-1992", "2175", "consolidare 11.11.2023", "2023-11-11"),
                  read("just_ro/og21-republished-wb20251111.html"))
        self.assertEqual(res.status, UNCHANGED)
        self.assertEqual(res.current.in_force_from, "2023-11-11")

    def test_base_form_without_consolidations(self):
        a = act("ro.oug.141-2021", "250054", "forma de bază, MO nr. 1248 din 30.12.2021", "2021-12-30")
        res = run(a, read("just_ro/oug141-base-wb20251212.html"))
        self.assertEqual(res.status, UNCHANGED)
        self.assertTrue(res.evidence.parser.endswith("base-form"))

    def test_deferred_application_is_new_future_not_in_force(self):
        res = run(act(**OUG18), read("just_ro/oug18-base-wb20260406.html"), today=dt.date(2026, 9, 26))
        self.assertEqual(res.status, NEW_FUTURE)
        self.assertEqual(res.current.in_force_from, "2026-06-19")
        self.assertEqual(res.next.in_force_from, "2026-09-27")

    def test_deferred_application_already_known_is_unchanged(self):
        a = act(**OUG18, nxt={"label": "aplicare de la 27.09.2026", "in_force_from": "2026-09-27"})
        self.assertEqual(run(a, read("just_ro/oug18-base-wb20260406.html"), today=dt.date(2026, 9, 26)).status,
                         UNCHANGED)

    def test_on_application_date_becomes_new_in_force(self):
        res = run(act(**OUG18), read("just_ro/oug18-base-wb20260406.html"), today=dt.date(2026, 9, 27))
        self.assertEqual(res.status, NEW_IN_FORCE)
        self.assertEqual(res.current.label, "aplicare de la 27.09.2026")

    def test_baseline_absent_is_never_unchanged(self):
        res = run(act(label="consolidare 20.07.2022 (archive copy)", date=None), read(OUG34))
        self.assertEqual(res.status, NEW_IN_FORCE)
        self.assertTrue(any("baseline absent" in n for n in res.notes))


class Synthetic(unittest.TestCase):
    def test_new_consolidation_in_force(self):
        res = run(act(), read("just_ro/new-in-force.html"))
        self.assertEqual(res.status, NEW_IN_FORCE)
        self.assertEqual(res.current.label, "consolidare 15.09.2026")
        self.assertEqual(res.current.doc_id, "399001")

    def test_future_consolidation_is_new_future(self):
        res = run(act(), read("just_ro/new-future.html"))
        self.assertEqual(res.status, NEW_FUTURE)
        self.assertEqual(res.current.label, "consolidare 20.07.2022")
        self.assertEqual(res.next.in_force_from, "2027-01-15")

    def test_repealed_act(self):
        res = run(act(), read("just_ro/repealed.html"))
        self.assertEqual(res.status, REPEALED)
        self.assertIn("LEGEA nr. 999", res.current.label)

    def test_future_repeal_is_new_future_not_repealed(self):
        res = run(act(), read("just_ro/repeal-future.html"))
        self.assertEqual(res.status, NEW_FUTURE)
        self.assertTrue(res.next.label.startswith("abrogare de la 01.03.2027"))

    def test_empty_or_truncated_is_parse_failed(self):
        for name in ("truncated.html", "empty.html"):
            res = run(act(), read(f"just_ro/{name}"))
            self.assertEqual(res.status, PARSE_FAILED, name)
            self.assertTrue(res.error)

    def test_no_dates_is_parse_failed(self):
        self.assertEqual(run(act(), read("just_ro/no-dates.html")).status, PARSE_FAILED)

    def test_wrong_act_page_is_parse_failed(self):
        res = run(act(), read("just_ro/oug141-base-wb20251212.html"))
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertIn("does not identify", res.error)

    def test_act_without_number_year_is_parse_failed(self):
        res = run(act(aid="ro.oug.x"), read(OUG34))
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertIn("no number/year", res.error)

    def test_page_older_than_baseline_is_parse_failed(self):
        self.assertEqual(run(act(label="consolidare 15.09.2026", date="2026-09-15"), read(OUG34)).status,
                         PARSE_FAILED)

    def test_cloudflare_challenge_is_blocked(self):
        res = run(act(), read("legis_md/cloudflare-challenge-2026-09-27.html"), status=403)
        self.assertEqual(res.status, BLOCKED_403)
        self.assertIn("not bypassed", res.error)

    def test_plain_403_is_blocked(self):
        self.assertEqual(run(act(), "<html><title>Forbidden</title><body>403</body></html>", status=403).status,
                         BLOCKED_403)

    def test_subresource_403_is_blocked(self):
        url = just_ro.PAGE_URL.format(doc_id="158913")
        r = FetchResult(url=url, status=200, html="<html></html>", text="x", fetched_at="t",
                        subresource_403=[url + "/x.js"])
        self.assertEqual(run(act(), result=r).status, BLOCKED_403)

    def test_portal_http2_error_is_fetch_failed(self):
        r = FetchResult(url=just_ro.PAGE_URL.format(doc_id="158913"), status=None, fetched_at="2026-09-27T18:27:18Z",
                        error="URLError: HTTP/2 protocol error")
        res = run(act(), result=r)
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertIn("HTTP/2", res.error)

    def test_http_500_is_fetch_failed(self):
        self.assertEqual(run(act(), "<html><body>err</body></html>", status=500).status, FETCH_FAILED)

    def test_source_without_doc_id_is_fetch_failed(self):
        a = {"id": "ro.lege.365-2002", "current": None, "next": None, "sources": [{"kind": "just_ro"}]}
        res = just_ro.check_act(a, FixtureFetcher({}), T)
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertIn("doc_id", res.error)

    def test_every_fixture_yields_known_status_never_unchanged_on_failure(self):
        for name in [OUG34.split("/")[1], "new-in-force.html", "new-future.html", "repealed.html",
                     "repeal-future.html", "no-dates.html", "truncated.html", "empty.html",
                     "oug141-base-wb20251212.html"]:
            d = run(act(), read(f"just_ro/{name}")).to_dict()
            self.assertIn(d["status"], STATUSES)
            if d["error"]:
                self.assertNotEqual(d["status"], UNCHANGED)


class CodePages(unittest.TestCase):
    def test_real_code_page_identified_and_unchanged(self):
        for kw, fx, n in [(CF, CF_HTML, 146), (CM, CM_HTML, 67)]:
            with self.subTest(code=kw["code"]):
                html = read(fx)
                page = just_ro.parse_just_html(html, re.sub(r"<[^>]+>", " ", html), kw["doc_id"], T)
                self.assertEqual(page.mode, "consolidations")
                self.assertEqual(len(page.redactions), n)
                res = run(act(**kw), html)
                self.assertEqual(res.status, UNCHANGED, res)
                self.assertEqual(res.current.label, kw["label"])
                self.assertEqual(res.current.doc_id, kw["doc_id"])

    def test_code_page_has_no_law_number_but_is_identified(self):
        html = read(CF_HTML)
        self.assertNotIn("227 08/09/2015", html)
        self.assertNotIn("nr. 227 din", html)
        self.assertTrue(just_ro.identifies_act(act(**CF), "COD FISCAL               08/09/2015 - Portal Legislativ",
                                               "CODUL FISCAL din 8 septembrie 2015"))

    def test_code_by_title_or_heading(self):
        self.assertTrue(just_ro.identifies_act(act(**CF), "COD FISCAL 08/09/2015 - Portal Legislativ", None))
        self.assertTrue(just_ro.identifies_act(act(**CF), "Portal Legislativ", "CODUL FISCAL din 8 septembrie 2015"))

    def test_code_identification_is_strict(self):
        cases = [
            (CF, "COD FISCAL 09/09/2015", "CODUL FISCAL din 9 septembrie 2015"),       # another date
            (CF, "COD PROCEDURA FISCALA 20/07/2015", "CODUL DE PROCEDURĂ FISCALĂ din 20 iulie 2015"),
            (CF, "CODUL MUNCII 24/01/2003", "CODUL MUNCII din 24 ianuarie 2003"),     # another code
            (CM, "COD FISCAL 08/09/2015", "CODUL FISCAL din 8 septembrie 2015"),
            (CF, "LEGE 227 08/09/2015", "LEGE nr. 227 din 8 septembrie 2015"),        # the approving law
            (CM, "LEGE 53 24/01/2003", "LEGEA nr. 53 din 24 ianuarie 2003"),
            (CF, "ORD 5 COD FISCAL 08/09/2015", "ORDIN privind CODUL FISCAL din 8 septembrie 2015"),
        ]
        for kw, title, heading in cases:
            with self.subTest(title=title):
                self.assertFalse(just_ro.identifies_act(act(**kw), title, heading))

    def test_approval_law_page_is_parse_failed_for_code(self):
        res = run(act(**CF), read("just_ro/lege227-approval-law.html"))
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertIn("does not identify ro.cod.fiscal", res.error)

    def test_other_code_page_is_parse_failed(self):
        res = run(act(**CF), read("just_ro/codprocfiscala-other-code.html"))
        self.assertEqual(res.status, PARSE_FAILED)

    def test_code_page_on_wrong_act_is_parse_failed(self):
        self.assertEqual(run(act(**CF), read(CM_HTML)).status, PARSE_FAILED)
        self.assertEqual(run(act(**CM), read(CF_HTML)).status, PARSE_FAILED)
        self.assertEqual(run(act(), read(CF_HTML)).status, PARSE_FAILED)

    def test_unknown_code_is_parse_failed(self):
        a = act(**dict(CF, code="civil"))
        res = run(a, read(CF_HTML))
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertIn("CODE_PAGES", res.error)
        self.assertFalse(just_ro.identifies_code_page("civil", "CODUL CIVIL 17/07/2009", None))

    def test_generic_act_unaffected_by_code_map(self):
        self.assertTrue(just_ro.identifies_act(act(), "OUG         34 04/06/2014 - Portal Legislativ", None))
        self.assertFalse(just_ro.identifies_act(act(), "COD FISCAL 08/09/2015", "CODUL FISCAL din 8 septembrie 2015"))

    def test_code_baseline_absent_is_new_in_force(self):
        res = run(act(**dict(CF, label=None)), read(CF_HTML))
        self.assertEqual(res.status, NEW_IN_FORCE)
        self.assertTrue(any("baseline absent" in n for n in res.notes))

    def test_new_code_consolidation_is_new_in_force(self):
        res = run(act(**dict(CF, label="consolidare 31.12.2025", date="2025-12-31")), read(CF_HTML))
        self.assertEqual(res.status, NEW_IN_FORCE)
        self.assertEqual(res.current.label, "consolidare 01.01.2026")

    def test_code_page_failures_never_unchanged(self):
        for kw, fx in [(CF, CF_HTML), (CM, CM_HTML)]:
            html = read(fx)
            for h, st in [(html[:1500], 200), (html, 500), (html, 403), (read("just_ro/empty.html"), 200)]:
                res = run(act(**kw), h, status=st)
                self.assertIn(res.status, (PARSE_FAILED, FETCH_FAILED, BLOCKED_403))
                self.assertTrue(res.error)

    def test_single_quoted_consolidation_markup_is_parsed(self):
        # The portal's raw bytes use single quotes; a browser serialises double quotes.
        html = read(CM_HTML)
        raw = re.sub(r'<a title="(Consolidarea din [\d.]+)" style="([^"]*)"(?: href="([^"]*)")?>',
                     lambda m: f"<a title='{m[1]}' style='{m[2]}'" + (f" href='{m[3]}'" if m[3] else "") + ">",
                     html)
        self.assertNotEqual(raw, html)
        a, b = run(act(**CM), html), run(act(**CM), raw)
        self.assertEqual(a.status, UNCHANGED)
        self.assertEqual(b.status, UNCHANGED)
        self.assertEqual(a.current, b.current)
        self.assertEqual(just_ro.parse_just_html(raw, "", "41627", T).displayed, "consolidare 18.12.2025")


def page_md_from_html(html: str) -> str:
    """A rough markdown of a portal page: consolidation links → [date](url), the rest as text."""
    t = re.sub(r'<a\b[^>]*href="[^"]*DetaliiDocument/(\d+)"[^>]*>(\d{2}\.\d{2}\.\d{4})</a>',
               r"[\2](https://legislatie.just.ro/Public/DetaliiDocument/\1)", html)
    return fixture_result("x", t).text


class MarkdownPath(unittest.TestCase):
    URL = just_ro.PAGE_URL.format(doc_id="158913")

    def run_md(self, md, today=T):
        r = fixture_result(self.URL, "", via="command", markdown=md)
        return just_ro.check_act(act(), FixtureFetcher({self.URL: r}), today)

    def test_markdown_parses_same_versions_uncalibrated(self):
        res = self.run_md(page_md_from_html(read(OUG34)))
        self.assertTrue(res.evidence.parser.startswith(just_ro.PARSER_ID_MD), res.evidence.parser)
        self.assertEqual(res.status, UNCHANGED, res.error)
        self.assertEqual(res.current.label, "consolidare 20.07.2022")
        self.assertEqual(res.current.doc_id, "158913")
        self.assertFalse(res.evidence.parser_calibrated)
        self.assertEqual(res.evidence.via, "command")
        self.assertTrue(any("markdown parser not calibrated" in n for n in res.notes))

    def test_future_form_shown_is_never_current(self):
        md = page_md_from_html(read(OUG34)).replace(
            "20.07.2022", "15.12.2026 [20.07.2022](https://legislatie.just.ro/Public/DetaliiDocument/261000)", 1)
        md = "Forma consolidată valabilă la 15.12.2026\n" + md
        res = self.run_md(md)
        self.assertEqual(res.current.in_force_from, "2022-07-20")
        self.assertEqual(res.next.in_force_from, "2026-12-15")
        self.assertEqual(res.status, NEW_FUTURE)
        self.assertTrue(any("future form" in n for n in res.notes))
        later = self.run_md(md, today=dt.date(2026, 12, 16))
        self.assertEqual(later.status, NEW_IN_FORCE)
        self.assertEqual(later.current.in_force_from, "2026-12-15")

    def test_markdown_modifiers_listed(self):
        md = ("# ORDONANȚĂ DE URGENȚĂ nr. 34 din 4 iunie 2014\nMONITORUL OFICIAL nr. 427 din 11 iunie 2014\n"
              "(la 27-09-2026, Articolul 11 a fost modificat de Punctul 4, Articolul I din ORDONANȚA DE URGENȚĂ nr. 18 "
              "din 25 martie 2026, publicată în MONITORUL OFICIAL nr. 236 din 26 martie 2026)\n"
              "modificat de LEGEA nr. 157 din 9 iunie 2022\n" + "text " * 600)
        p = just_ro.parse_just_markdown(md, md_to_text(md), "158913", T)
        self.assertTrue(p.heading.startswith("ORDONANȚĂ DE URGENȚĂ nr. 34 din 4 iunie 2014"))
        self.assertTrue(any("ORDONANȚA DE URGENȚĂ nr. 18" in m for m in p.modifiers))
        self.assertTrue(any("LEGEA nr. 157" in m for m in p.modifiers))
        self.assertEqual(p.mode, "base-form")
        self.assertEqual(p.redactions[0].in_force_from, "2014-06-11")
        res = self.run_md(md)
        self.assertTrue(any(n.startswith("amending acts named on the page") for n in res.notes))

    def test_modifiers_are_capped(self):
        body = " ".join(f"modificat de LEGEA nr. {i} din 1 mai 2020;" for i in range(50))
        self.assertEqual(len(just_ro.modifying_acts(body)), 40)

    def test_page_with_many_modifiers_notes_the_rest(self):
        md = ("# ORDONANȚĂ DE URGENȚĂ nr. 34 din 4 iunie 2014\nMONITORUL OFICIAL nr. 427 din 11 iunie 2014\n"
              + " ".join(f"modificat de LEGEA nr. {i} din 1 mai 2020;" for i in range(20)) + " text" * 600)
        res = self.run_md(md)
        self.assertTrue(any("(+5)" in n for n in res.notes))

    def test_markdown_without_dates_is_parse_failed(self):
        md = "# ORDONANȚĂ DE URGENȚĂ nr. 34 din 4 iunie 2014\n" + "text " * 600
        self.assertEqual(self.run_md(md).status, PARSE_FAILED)

    def test_future_only_page_is_parse_failed(self):
        md = ("# ORDONANȚĂ DE URGENȚĂ nr. 34 din 4 iunie 2014\nse aplică începând cu data de 1 ianuarie 2030\n"
              + "text " * 600)
        res = self.run_md(md)
        self.assertEqual(res.status, PARSE_FAILED)


if __name__ == "__main__":
    unittest.main()
