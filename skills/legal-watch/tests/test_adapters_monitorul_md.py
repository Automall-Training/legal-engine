"""monitorul_md scan: live snapshots of the home page and one issue + a synthetic issue with a mention. No network."""
import datetime as dt
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from watch.adapters import monitorul_md as mo  # noqa: E402
from watch.contract import BLOCKED_403, FETCH_FAILED, PARSE_FAILED, SCAN_COMPLETE  # noqa: E402
from watch.fetchers import FetchResult, FixtureFetcher, fixture_result  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
TODAY = dt.date(2026, 9, 28)


def read(rel: str) -> str:
    return (FIX / rel).read_text(encoding="utf-8")


HOME = read("monitorul_md/home-2026-09-27.html")
ED3350 = read("monitorul_md/edition-3350-2026-09-27.html")
ACTS = [
    {"id": "md.cod.muncii", "jurisdiction": "MD", "number": "154", "year": "2003", "code": "muncii"},
    {"id": "md.lege.105-2003", "jurisdiction": "MD"},
    {"id": "md.hg.771-2025", "jurisdiction": "MD"},
    {"id": "ro.oug.34-2014", "jurisdiction": "RO"},
]


def synthetic_3351(line="502. Lege pentru modificarea Codului muncii al Republicii Moldova nr. 154/2003 "
                        "(nr. 999, 18 septembrie 2026) [SYNTHETIC]"):
    """SYNTHETIC: the 3350 snapshot with another number and one extra table-of-contents line."""
    h = ED3350.replace("<h2>Monitorul Oficial Nr. 481-482</h2>", "<h2>Monitorul Oficial Nr. 483-485</h2>")
    return h.replace("<div>501. Lege privind", f"<div>{line}</div>\n<div>&nbsp;</div>\n<div>501. Lege privind", 1)


def pages(**over):
    m = {mo.HOME_URL: fixture_result(mo.HOME_URL, HOME),
         mo.EDITION_URL.format(id=3350): fixture_result(mo.EDITION_URL.format(id=3350), ED3350),
         mo.EDITION_URL.format(id=3351): fixture_result(mo.EDITION_URL.format(id=3351), synthetic_3351())}
    m.update(over)
    return FixtureFetcher(m)


class Parse(unittest.TestCase):
    def test_home_is_not_mistaken_for_captcha(self):
        # The home page carries a reCAPTCHA form widget but is a full page.
        self.assertFalse(fixture_result(mo.HOME_URL, HOME).blocked)

    def test_parse_home(self):
        recent = mo.parse_home(HOME)
        self.assertEqual(max(recent), 3351)
        self.assertEqual(min(recent), 3342)
        self.assertEqual(recent[3350], {"number": "481-482", "date": "2026-09-24"})

    def test_parse_edition(self):
        num, date, items = mo.parse_edition(ED3350, fixture_result("u", ED3350).text)
        self.assertEqual(num, "481-482")
        self.assertEqual(date, "2026-09-24")
        self.assertEqual(len(items), 6)
        self.assertTrue(items[1].startswith("497. Lege pentru modificarea Legii bugetului"))

    def test_act_patterns(self):
        p = mo.act_patterns({"id": "md.hg.771-2025", "jurisdiction": "MD"})
        self.assertTrue(mo.match_act("Hotărâre pentru modificarea Hotărârii Guvernului nr. 771/2025 (nr. 1)", p))
        self.assertFalse(mo.match_act("Hotărâre ... nr. 1771/2025", p))
        self.assertFalse(mo.match_act("Hotărâre ... nr. 771/2024", p))
        self.assertEqual(mo.act_patterns({"id": "ro.oug.34-2014", "jurisdiction": "RO"}), [])
        self.assertEqual(mo.act_patterns({"id": "md.x", "jurisdiction": "MD"}), [])

    def test_code_name_from_act_code(self):
        p = mo.act_patterns({"id": "md.cod.fiscal", "jurisdiction": "MD", "code": "fiscal"})
        self.assertEqual(len(p), 1)
        self.assertEqual(mo.match_act("Lege pentru modificarea Codului fiscal (nr. 5, 1 octombrie 2026)", p),
                         "Codului fiscal")
        self.assertEqual(mo.act_patterns({"id": "md.cod.x", "jurisdiction": "MD", "code": "unknown"}), [])


class Scan(unittest.TestCase):
    def test_new_editions_with_signal(self):
        f = pages()
        res = mo.scan(ACTS, f, since=3349, today=TODAY)
        self.assertEqual(res.status, SCAN_COMPLETE)
        self.assertIsNone(res.error)
        self.assertEqual([e.edition_id for e in res.editions], [3350, 3351])
        self.assertEqual(res.checked_through, 3351)
        self.assertEqual(res.previous_checked_through, 3349)
        self.assertEqual(len(res.signals), 1)
        s = res.signals[0]
        self.assertEqual(s.act_id, "md.cod.muncii")
        self.assertEqual(s.edition_id, 3351)
        self.assertIn("SYNTHETIC", s.item)
        self.assertEqual(f.calls[0], mo.HOME_URL)       # home first, then issues in order
        self.assertEqual(res.evidence.via, "fixture")

    def test_code_named_without_number_gives_signal(self):
        line = "503. Lege pentru modificarea Codului muncii (nr. 998, 18 septembrie 2026) [SYNTHETIC]"
        f = pages(**{mo.EDITION_URL.format(id=3351): fixture_result("u", synthetic_3351(line))})
        res = mo.scan(ACTS, f, since=3350, today=TODAY)
        self.assertEqual([s.matched for s in res.signals], ["Codului muncii"])

    def test_real_edition_has_no_false_signal(self):
        res = mo.scan(ACTS, pages(), since=3349, today=TODAY)
        self.assertFalse([s for s in res.signals if s.edition_id == 3350])

    def test_nothing_new_is_complete_without_editions(self):
        res = mo.scan(ACTS, pages(), since=3351, today=TODAY)
        self.assertEqual(res.status, SCAN_COMPLETE)
        self.assertEqual(res.editions, [])
        self.assertEqual(res.checked_through, 3351)

    def test_failed_edition_stops_progress_without_skipping(self):
        bad = FetchResult(url=mo.EDITION_URL.format(id=3350), status=None, fetched_at="t", error="timed out")
        res = mo.scan(ACTS, pages(**{mo.EDITION_URL.format(id=3350): bad}), since=3349, today=TODAY)
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertEqual(res.checked_through, 3349)
        self.assertEqual(res.editions, [])

    def test_second_edition_fails_first_counted(self):
        res = mo.scan(ACTS, pages(**{mo.EDITION_URL.format(id=3351): fixture_result("u", "<html>x</html>",
                                                                                     status=404)}),
                      since=3349, today=TODAY)
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertEqual(res.checked_through, 3350)

    def test_blocked_edition(self):
        cf = read("legis_md/cloudflare-challenge-2026-09-27.html")
        res = mo.scan(ACTS, pages(**{mo.EDITION_URL.format(id=3350): fixture_result("u", cf, status=403)}),
                      since=3349, today=TODAY)
        self.assertEqual(res.status, BLOCKED_403)
        self.assertEqual(res.checked_through, 3349)

    def test_home_blocked(self):
        cf = read("legis_md/cloudflare-challenge-2026-09-27.html")
        res = mo.scan(ACTS, pages(**{mo.HOME_URL: fixture_result(mo.HOME_URL, cf, status=403)}), since=3349,
                      today=TODAY)
        self.assertEqual(res.status, BLOCKED_403)
        self.assertEqual(res.checked_through, 3349)

    def test_home_network_failure_and_http_error(self):
        bad = FetchResult(url=mo.HOME_URL, status=None, fetched_at="t", error="name not resolved")
        self.assertEqual(mo.scan(ACTS, pages(**{mo.HOME_URL: bad}), since=3349, today=TODAY).status, FETCH_FAILED)
        err = fixture_result(mo.HOME_URL, "<html><body>err</body></html>", status=500)
        self.assertEqual(mo.scan(ACTS, pages(**{mo.HOME_URL: err}), since=3349, today=TODAY).status, FETCH_FAILED)

    def test_home_structure_changed_is_parse_failed(self):
        page = fixture_result(mo.HOME_URL, "<html><body>" + "x" * 3000 + "</body></html>")
        self.assertEqual(mo.scan(ACTS, pages(**{mo.HOME_URL: page}), since=3349, today=TODAY).status, PARSE_FAILED)

    def test_home_older_than_checked_through_is_parse_failed(self):
        res = mo.scan(ACTS, pages(), since=3400, today=TODAY)
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertEqual(res.checked_through, 3400)

    def test_edition_structure_changed_is_parse_failed(self):
        page = fixture_result("u", "<html><body>" + "x" * 3000 + "</body></html>")
        res = mo.scan(ACTS, pages(**{mo.EDITION_URL.format(id=3350): page}), since=3349, today=TODAY)
        self.assertEqual(res.status, PARSE_FAILED)
        self.assertEqual(res.checked_through, 3349)

    def test_cap_on_editions_is_loud(self):
        res = mo.scan(ACTS, pages(), since=3349, today=TODAY, max_editions=1)
        self.assertEqual(res.status, FETCH_FAILED)
        self.assertEqual(res.checked_through, 3350)
        self.assertIn("continue next run", res.error)

    def test_first_run_baseline_uses_home_editions(self):
        m = {mo.HOME_URL: fixture_result(mo.HOME_URL, HOME)}
        for i in range(3342, 3352):
            m[mo.EDITION_URL.format(id=i)] = fixture_result("u", ED3350)
        res = mo.scan(ACTS, FixtureFetcher(m), since=None, today=TODAY)
        self.assertEqual(res.status, SCAN_COMPLETE)
        self.assertIsNone(res.previous_checked_through)
        self.assertEqual(res.checked_through, 3351)

    def test_scan_serialises(self):
        d = mo.scan(ACTS, pages(), since=3349, today=TODAY).to_dict()
        self.assertEqual(d["status"], "complete")
        self.assertEqual(d["signals"][0]["act_id"], "md.cod.muncii")


if __name__ == "__main__":
    unittest.main()
