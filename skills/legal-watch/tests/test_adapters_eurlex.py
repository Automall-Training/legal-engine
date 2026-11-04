"""eurlex adapter (and its Cellar fallback): saved page → status. No network.

EUR-Lex fixtures are live excerpts (scripts and stylesheets removed); no-force-indicator.html is synthetic.
Cellar fixtures `cellar-*.json` are live SPARQL + text answers keyed by URL. Every Cellar call goes through an
injected getter, so the tests never reach the network.
"""
import copy
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from watch.adapters import cellar, eurlex  # noqa: E402
from watch.contract import (BLOCKED_403, FETCH_FAILED, NEW_FUTURE, NEW_IN_FORCE, PARSE_FAILED,  # noqa: E402
                            REPEALED, STATUSES, UNCHANGED)
from watch.fetchers import FetchResult, FixtureFetcher, fixture_result  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
T = dt.date(2026, 9, 28)
DIR_2011_83 = "eurlex/32011L0083-all-2026-09-27.html"


def read(rel: str) -> str:
    return (FIX / rel).read_text(encoding="utf-8")


def no_network(url, headers, timeout=90):
    raise RuntimeError("network disabled in tests")



def act(aid, celex, label=None, date=None, nxt=None, url=None):
    src = {"kind": "eurlex"}
    if celex:
        src["celex"] = celex
    if url:
        src["url"] = url
    return {"id": aid, "jurisdiction": "EU", "priority": "p1",
            "current": {"label": label, "in_force_from": date} if label else None, "next": nxt, "sources": [src]}


def run(a, html=None, *, status=200, result=None, today=T, cellar_get=no_network):
    url = eurlex.PAGE_URL.format(celex=eurlex.celex_of(a))
    r = result if result is not None else fixture_result(url, html, status=status)
    return eurlex.check_act(a, FixtureFetcher({url: r}), today, cellar_get=cellar_get)


class Page(unittest.TestCase):
    def test_celex_from_celex_doc_id_url_and_eli(self):
        self.assertEqual(eurlex.celex_of(act("x", "32011L0083")), "32011L0083")
        self.assertEqual(eurlex.celex_of({"sources": [{"kind": "eurlex", "doc_id": "CELEX 32011L0083"}]}),
                         "32011L0083")
        self.assertEqual(eurlex.celex_of(act("x", None, url="https://eur-lex.europa.eu/eli/reg/2016/679/oj")),
                         "32016R0679")
        self.assertIsNone(eurlex.celex_of(act("x", None, url="https://eur-lex.europa.eu/legal-content/EN/TXT/"
                                                             "?uri=CELEX:02011L0083-20220528")))
        self.assertIsNone(eurlex.celex_of({"sources": [{"kind": "legis_md", "doc_id": "1"}]}))

    def test_future_consolidation_before_its_date_is_new_future(self):
        res = run(act("eu.dir.2011-83", "32011L0083", "consolidare 28.05.2022", "2022-05-28"), read(DIR_2011_83),
                  today=dt.date(2026, 9, 26))
        self.assertEqual(res.status, NEW_FUTURE)
        self.assertEqual(res.current.label, "consolidare 28.05.2022")
        self.assertEqual(res.next.in_force_from, "2026-09-27")
        self.assertEqual(res.next.doc_id, "02011L0083-20260927")

    def test_new_consolidation_in_force(self):
        res = run(act("eu.dir.2011-83", "32011L0083", "consolidare 28.05.2022", "2022-05-28"), read(DIR_2011_83))
        self.assertEqual(res.status, NEW_IN_FORCE)
        self.assertEqual(res.current.label, "consolidare 27.09.2026")
        self.assertTrue(any("Current consolidated version" in n for n in res.notes))
        self.assertFalse(any("HTTP 202" in n for n in res.notes))

    def test_known_consolidation_unchanged(self):
        res = run(act("eu.dir.2011-83", "32011L0083", "consolidare 27.09.2026", "2026-09-27"), read(DIR_2011_83))
        self.assertEqual(res.status, UNCHANGED)
        self.assertTrue(res.evidence.parser.endswith("consolidations"))
        self.assertTrue(res.evidence.parser_calibrated)
        self.assertEqual(len(res.evidence.sha256), 64)
        self.assertEqual(res.evidence.via, "fixture")

    def test_gdpr_unchanged(self):
        res = run(act("eu.reg.2016-679", "32016R0679", "consolidare 04.05.2016", "2016-05-04"),
                  read("eurlex/32016R0679-all-2026-09-27.html"))
        self.assertEqual(res.status, UNCHANGED)

    def test_base_form_and_future_transposition(self):
        a = act("eu.dir.2023-2673", "32023L2673", "forma de bază", "2023-12-18")
        html = read("eurlex/32023L2673-all-2026-09-27.html")
        self.assertEqual(run(a, html).status, UNCHANGED)
        res = run(a, html, today=dt.date(2026, 6, 1))
        self.assertEqual(res.status, NEW_FUTURE)
        self.assertEqual(res.next.in_force_from, "2026-06-19")

    def test_future_date_of_application_is_new_future(self):
        a = act("eu.reg.2024-1689", "32024R1689", "consolidare 27.07.2026", "2026-07-27")
        res = run(a, read("eurlex/32024R1689-all-2026-09-27.html"))
        self.assertEqual(res.status, NEW_FUTURE)
        self.assertEqual(res.next.in_force_from, "2027-08-02")
        self.assertEqual(res.current.label, "consolidare 27.07.2026")

    def test_repealed_act(self):
        res = run(act("eu.dir.1997-7", "31997L0007", "consolidare 13.06.2014", "2014-06-13"),
                  read("eurlex/31997L0007-all-2026-09-27.html"), status=202)
        self.assertEqual(res.status, REPEALED)
        self.assertIn("32011L0083", res.current.label)
        self.assertIn("13.06.2014", res.current.label)

    def test_baseline_absent_is_never_unchanged(self):
        res = run(act("eu.dir.2023-2673", "32023L2673"), read("eurlex/32023L2673-all-2026-09-27.html"))
        self.assertEqual(res.status, NEW_IN_FORCE)
        self.assertTrue(any("baseline absent" in n for n in res.notes))

    def test_202_with_full_body_is_read_and_noted(self):
        res = run(act("eu.dir.2011-83", "32011L0083", "consolidare 27.09.2026", "2026-09-27"), read(DIR_2011_83), status=202)
        self.assertEqual(res.status, UNCHANGED)
        self.assertTrue(any("HTTP 202" in n for n in res.notes))

    def test_waf_202_empty_body_is_blocked_and_cellar_failure_noted(self):
        a = act("eu.dir.2011-83", "32011L0083", "consolidare 28.05.2022", "2022-05-28")
        url = eurlex.PAGE_URL.format(celex="32011L0083")
        r = FetchResult(url=url, status=202, final_url=url, html="", text="", fetched_at="t")
        res = run(a, result=r)
        self.assertEqual(res.status, BLOCKED_403)
        self.assertIn("AWS WAF", res.error)
        self.assertTrue(any(n.startswith("cellar fallback: fetch_failed") for n in res.notes))

    def test_cellar_fallback_can_be_switched_off(self):
        a = act("eu.dir.2011-83", "32011L0083")
        url = eurlex.PAGE_URL.format(celex="32011L0083")
        r = FetchResult(url=url, status=None, fetched_at="t", error="TimeoutError")
        res = eurlex.check_act(a, FixtureFetcher({url: r}), T, cellar_fallback=False)
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertEqual(res.notes, [])

    def test_cloudflare_or_403_is_blocked(self):
        a = act("eu.dir.2011-83", "32011L0083")
        self.assertEqual(run(a, read("legis_md/cloudflare-challenge-2026-09-27.html"), status=403).status,
                         BLOCKED_403)
        self.assertEqual(run(a, "<html><title>Forbidden</title><body>no</body></html>", status=403).status,
                         BLOCKED_403)

    def test_no_force_indicator_is_parse_failed(self):
        res = run(act("eu.dir.2011-83", "32011L0083", "consolidare 28.05.2022", "2022-05-28"),
                  read("eurlex/no-force-indicator.html"))
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertIn("forceIndicator", res.error)

    def test_unknown_force_text_is_parse_failed(self):
        # A status text that is neither "In force" nor "No longer in force" gives no versions.
        html = HTML_914.replace('<p class="forceIndicator">In force</p>', '<p class="forceIndicator">Unclear</p>')
        url = eurlex.PAGE_URL.format(celex="32021D0914")
        res = eurlex.check_act(act_914(), FixtureFetcher({url: fixture_result(url, html)}), T, cellar_get=no_network)
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertIn("no consolidation or date of effect", res.error)

    def test_empty_or_truncated_is_parse_failed(self):
        for html in ("", "<html><title>Directive - 2011/83 - EN</title><body>short</body></html>"):
            self.assertEqual(run(act("eu.dir.2011-83", "32011L0083"), html).status, PARSE_FAILED)

    def test_markdown_only_engine_is_fetch_failed(self):
        a = act("eu.dir.2011-83", "32011L0083")
        url = eurlex.PAGE_URL.format(celex="32011L0083")
        r = fixture_result(url, "", via="command", markdown="# Directive 2011/83\n" + "text " * 600)
        res = run(a, result=r)
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertIn("markdown", res.error)

    def test_wrong_act_page_is_parse_failed(self):
        res = run(act("eu.dir.2011-83", "32011L0083"), read("eurlex/32016R0679-all-2026-09-27.html"))
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertIn("does not identify", res.error)

    def test_page_older_than_baseline_is_parse_failed(self):
        a = act("eu.reg.2016-679", "32016R0679", "consolidare 01.09.2026", "2026-09-01")
        self.assertEqual(run(a, read("eurlex/32016R0679-all-2026-09-27.html")).status, PARSE_FAILED)

    def test_network_failure_and_http_500_are_fetch_failed(self):
        a = act("eu.dir.2011-83", "32011L0083")
        url = eurlex.PAGE_URL.format(celex="32011L0083")
        r = FetchResult(url=url, status=None, fetched_at="t", error="TimeoutError: timed out")
        self.assertEqual(run(a, result=r).status, FETCH_FAILED)
        self.assertEqual(run(a, "<html><body>err</body></html>", status=500).status, FETCH_FAILED)

    def test_source_without_celex_is_fetch_failed(self):
        a = {"id": "eu.x", "current": None, "sources": [{"kind": "eurlex", "url": "https://eur-lex.europa.eu/"}]}
        res = eurlex.check_act(a, FixtureFetcher({}), T, cellar_get=no_network)
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertIn("CELEX", res.error)

    def test_every_fixture_yields_known_status(self):
        a = act("eu.dir.2011-83", "32011L0083", "consolidare 28.05.2022", "2022-05-28")
        for name in ["32011L0083-all-2026-09-27.html", "32016R0679-all-2026-09-27.html", "no-force-indicator.html"]:
            d = run(a, read(f"eurlex/{name}")).to_dict()
            self.assertIn(d["status"], STATUSES)
            if d["error"]:
                self.assertNotEqual(d["status"], UNCHANGED)


HTML_914 = """<html><head><title>Decision - 2021/914 - EN - EUR-Lex</title></head><body>
<p class="forceIndicator">In force</p>
<dl><dt>Date of document: </dt><dd>04/06/2021</dd>
<dt>Date of effect: </dt><dd>27/06/2021; Entry into force Date pub. +20 See Art 4</dd>
<dt>Date of end of validity: </dt><dd>No end date</dd></dl>
<a data-celex="02021D0914-20210607">consolidated 07/06/2021</a>
""" + ("<p>Standard contractual clauses for the transfer of personal data to third countries.</p>" * 40) \
    + "</body></html>"   # SYNTHETIC, shaped like the live page


def act_914():
    return act("eu.dec.2021-914", "32021D0914", "forma de bază (text inițial, JO L 199/07.06.2021)", "2021-06-27")


def act_gdpr():
    return act("eu.reg.2016-679", "32016R0679", "consolidare 04.05.2016", "2016-05-04")


class PreEffectConsolidation(unittest.TestCase):
    def test_pre_effect_consolidation_is_base_form(self):
        url = eurlex.PAGE_URL.format(celex="32021D0914")
        res = eurlex.check_act(act_914(), FixtureFetcher({url: fixture_result(url, HTML_914)}), T)
        self.assertEqual(res.status, UNCHANGED, res.error)
        self.assertEqual(res.current.label, "forma de bază")
        self.assertEqual(res.current.in_force_from, "2021-06-27")
        later = HTML_914.replace('data-celex="02021D0914-20210607"', 'data-celex="02021D0914-20250101"')
        res2 = eurlex.check_act(act_914(), FixtureFetcher({url: fixture_result(url, later)}), T)
        self.assertEqual(res2.status, NEW_IN_FORCE)
        self.assertEqual(res2.current.in_force_from, "2025-01-01")

    def test_fold_keeps_later_consolidations(self):
        both = HTML_914.replace('<a data-celex="02021D0914-20210607">',
                                '<a data-celex="02021D0914-20250101">x</a><a data-celex="02021D0914-20210607">')
        p = eurlex.parse_eurlex(both, "32021D0914", T)
        eurlex.fold_preeffect_consolidation(p, act_914(), "32021D0914")
        self.assertEqual([r.in_force_from for r in p["redactions"]], ["2025-01-01"])

    def test_not_folded_for_consolidation_baseline(self):
        p = eurlex.parse_eurlex(HTML_914, "32021D0914", T)
        eurlex.fold_preeffect_consolidation(p, act("x", "32021D0914", "consolidare 07.06.2021", "2021-06-07"),
                                            "32021D0914")
        self.assertEqual(p["mode"], "consolidations")

    def test_end_of_validity_in_future_is_future_version(self):
        html = HTML_914.replace("<dd>No end date</dd>", "<dd>31/12/2030</dd>")
        p = eurlex.parse_eurlex(html, "32021D0914", T)
        self.assertTrue(any(r.label.startswith("sfârșitul valabilității") for r in p["redactions"]))

    def test_effect_without_consolidations_is_base_form_or_future_only(self):
        html = HTML_914.replace('<a data-celex="02021D0914-20210607">consolidated 07/06/2021</a>', "")
        self.assertEqual(eurlex.parse_eurlex(html, "32021D0914", T)["mode"], "base-form")
        none = html.replace("<dt>Date of effect: </dt><dd>27/06/2021; Entry into force Date pub. +20 See Art 4</dd>",
                            "")
        self.assertEqual(eurlex.parse_eurlex(none, "32021D0914", T)["mode"], "none")
        url = eurlex.PAGE_URL.format(celex="32021D0914")
        res = eurlex.check_act(act_914(), FixtureFetcher({url: fixture_result(url, none)}), T, cellar_get=no_network)
        self.assertEqual(res.status, PARSE_FAILED)


# ---------------------------------------------------------------- Cellar

T_CELLAR = dt.date(2026, 10, 2)


def cellar_get(celex, mutate=None):
    data = json.loads((FIX / "eurlex" / f"cellar-{celex}-2026-10-02.json").read_text(encoding="utf-8"))["responses"]
    if mutate:
        data = mutate(copy.deepcopy(data))
    calls = []

    def get(url, headers, timeout=90):
        calls.append((url, headers))
        if url not in data:
            raise RuntimeError("no fixture for url")
        st, fin, body = data[url]
        return st, fin, body

    get.calls = calls
    get.via = "fixture"
    return get


def waf(a):
    url = eurlex.PAGE_URL.format(celex=eurlex.celex_of(a))
    return FixtureFetcher({url: fixture_result(url, "<html><title></title><body></body></html>", status=202)})


def sparql_fwd_mutate(fn):
    def m(data):
        for url, v in data.items():
            if "sparql" in url and "date_end" in url.replace("%2D", "-") and "%3Fo" in url:
                body = json.loads(v[2])
                fn(body["results"]["bindings"])
                v[2] = json.dumps(body)
        return data
    return m


class Cellar(unittest.TestCase):
    def test_waf_falls_back_to_cellar(self):
        for a, celex in [(act_914(), "32021D0914"), (act_gdpr(), "32016R0679")]:
            with self.subTest(celex=celex):
                get = cellar_get(celex)
                res = eurlex.check_act(a, waf(a), T_CELLAR, cellar_get=get)
                self.assertEqual(res.status, UNCHANGED, (res.error, res.notes))
                self.assertEqual(res.adapter, "eurlex")
                self.assertTrue(res.evidence.parser.startswith(cellar.PARSER_ID))
                self.assertTrue(res.evidence.parser_calibrated)
                self.assertEqual(res.evidence.via, "fixture")
                self.assertTrue(res.evidence.url.startswith("http://publications.europa.eu/resource/celex/"))
                self.assertTrue(any("AWS WAF challenge" in n for n in res.notes))
                text_calls = [h for u, h in get.calls if "/resource/celex/" in u]
                self.assertEqual(text_calls[0]["Accept"], "application/xhtml+xml")
                self.assertEqual(text_calls[0]["Accept-Language"], "ron")
                self.assertEqual(res.current.in_force_from, a["current"]["in_force_from"])

    def test_cellar_keeps_base_form_and_gdpr_consolidation(self):
        r914 = eurlex.check_act(act_914(), waf(act_914()), T_CELLAR, cellar_get=cellar_get("32021D0914"))
        self.assertEqual(r914.current.label, "forma de bază")
        self.assertTrue(any("folded into the base text" in n for n in r914.notes))
        gdpr = eurlex.check_act(act_gdpr(), waf(act_gdpr()), T_CELLAR, cellar_get=cellar_get("32016R0679"))
        self.assertEqual(gdpr.current.label, "consolidare 04.05.2016")
        self.assertEqual(gdpr.current.doc_id, "02016R0679-20160504")
        self.assertTrue(any("amendment proposals" in n for n in gdpr.notes))

    def test_eurlex_ok_does_not_touch_cellar(self):
        url = eurlex.PAGE_URL.format(celex="32016R0679")
        get = cellar_get("32016R0679")
        eurlex.check_act(act_gdpr(), FixtureFetcher({url: fixture_result(url, read("eurlex/32016R0679-all-2026-09-27.html"))}),
                         T, cellar_get=get)
        self.assertEqual(get.calls, [])

    def test_repealed_and_future_entry(self):
        def ended(b):
            for x in b:
                if x["p"]["value"].endswith("date_end-of-validity"):
                    x["o"]["value"] = "2026-06-30"
        res = eurlex.check_act(act_914(), waf(act_914()), T_CELLAR,
                               cellar_get=cellar_get("32021D0914", sparql_fwd_mutate(ended)))
        self.assertEqual(res.status, REPEALED)
        self.assertIn("30.06.2026", res.current.label)

        def future(b):
            b.append({"p": {"value": "http://publications.europa.eu/ontology/cdm#resource_legal_date_entry-into-force"},
                      "o": {"value": "2027-01-01"}})
        res2 = eurlex.check_act(act_914(), waf(act_914()), T_CELLAR,
                                cellar_get=cellar_get("32021D0914", sparql_fwd_mutate(future)))
        self.assertEqual(res2.status, NEW_FUTURE)
        self.assertEqual(res2.next.in_force_from, "2027-01-01")
        self.assertEqual(res2.current.in_force_from, "2021-06-27")

    def test_sparql_http_error_is_fetch_failed(self):
        res = cellar.check_act(act_914(), T_CELLAR, get=lambda u, h: (500, u, "err"))
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertIn("SPARQL HTTP 500", res.error)
        self.assertEqual(res.evidence.via, "urllib")

    def test_sparql_unreadable_is_fetch_failed(self):
        res = cellar.check_act(act_914(), T_CELLAR, get=lambda u, h: (200, u, "not json"))
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertIn("unreadable", res.error)

    def test_work_not_found_is_parse_failed(self):
        empty = json.dumps({"results": {"bindings": []}})
        res = cellar.check_act(act_914(), T_CELLAR, get=lambda u, h: (200, u, empty))
        self.assertEqual(res.status, PARSE_FAILED)

    def test_no_celex_is_fetch_failed(self):
        res = cellar.check_act({"id": "eu.x", "sources": []}, T_CELLAR, get=no_network)
        self.assertEqual(res.status, FETCH_FAILED)

    def _with_text(self, celex, text_answer):
        base = cellar_get(celex)

        def get(url, headers, timeout=90):
            if "/resource/celex/" in url:
                if isinstance(text_answer, Exception):
                    raise text_answer
                return text_answer
            return base(url, headers)
        return get

    def test_text_not_delivered_is_fetch_failed(self):
        res = cellar.check_act(act_gdpr(), T_CELLAR, get=self._with_text("32016R0679", RuntimeError("down")))
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertIn("not delivered", res.error)

    def test_text_too_short_or_wrong_act_is_parse_failed(self):
        short = (200, "u", "<html><title>x</title><body>2016/679</body></html>")
        self.assertEqual(cellar.check_act(act_gdpr(), T_CELLAR, get=self._with_text("32016R0679", short)).status,
                         PARSE_FAILED)
        wrong = (200, "u", "<html><body>" + "Regulamentul 2011/83 " * 200 + "</body></html>")
        res = cellar.check_act(act_gdpr(), T_CELLAR, get=self._with_text("32016R0679", wrong))
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertIn("does not identify", res.error)

    def test_redactions_from_metadata_shapes(self):
        meta = {"in_force": False, "end": None, "entry": ["2020-01-01"], "consolidations": {},
                "repealed_by": [], "amended_by": ["32022R0001"], "corrections": ["32020R0001R(01)"], "proposals": []}
        p = cellar.redactions_from(meta, act("x", "32019R0001"), "32019R0001", T)
        self.assertEqual(p["mode"], "cellar-base-form")
        self.assertTrue(any("in-force = 0" in n for n in p["notes"]))
        self.assertTrue(any("amending acts" in n for n in p["notes"]))
        self.assertTrue(any("corrigenda" in n for n in p["notes"]))
        meta.update(in_force=None, entry=["2030-01-01"], amended_by=[], corrections=[], end="2031-01-01")
        p2 = cellar.redactions_from(meta, act("x", "32019R0001"), "32019R0001", T)
        self.assertEqual(p2["mode"], "cellar-future-only")
        meta.update(entry=[], end=None)
        p3 = cellar.redactions_from(meta, act("x", "32019R0001"), "32019R0001", T)
        self.assertEqual(p3["mode"], "cellar-none")
        meta.update(in_force=False, repealed_by=["32024R0002"])
        p4 = cellar.redactions_from(meta, act("x", "32019R0001"), "32019R0001", T)
        self.assertTrue(p4["repealed"])
        self.assertIn("32024R0002", p4["repealed_label"])

    def test_no_redactions_from_cellar_is_parse_failed(self):
        def none(b):
            b[:] = [x for x in b if not x["p"]["value"].endswith("entry-into-force")]

        def drop_cons(data):
            for url, v in data.items():
                if "sparql" in url and "%3Fsc" in url:
                    v[2] = json.dumps({"results": {"bindings": []}})
            return sparql_fwd_mutate(none)(data)
        get = cellar_get("32021D0914", drop_cons)
        res = cellar.check_act(act_914(), T_CELLAR, get=get)
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertIn("no consolidation", res.error)

    def test_default_getter_is_urllib(self):
        self.assertEqual(cellar.urllib_get.via, "urllib")
        self.assertIn("query=", cellar.sparql_url("SELECT 1"))


if __name__ == "__main__":
    unittest.main()
