"""Watchlist, catalog suggestion, act resolution, snapshots, the clause scanner and the fetch engines."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))
from watch import clauses, library as lib, schedule  # noqa: E402
from watch import fetchers as F  # noqa: E402

NICHES = {"general": ["civil"], "b2c": ["consumer"],
          "categories": {"civil": {"label": {"en": "Civil"}, "acts": ["md.cod.civil", "ro.lege.287-2009"]},
                         "consumer": {"label": {"en": "Consumers"}, "acts": ["ro.oug.34-2014", "eu.dir.2011-83"]},
                         "edu": {"label": {"en": "Education"}, "acts": ["md.cod.educatiei"]}},
          "niches": {"school": {"label": {"en": "School"}, "categories": ["edu"]}}}
ACTS = {i: {"id": i, "jurisdiction": i[:2].upper(), "title": i} for i in
        ("md.cod.civil", "ro.lege.287-2009", "ro.oug.34-2014", "eu.dir.2011-83", "md.cod.educatiei")}


class Suggest(unittest.TestCase):
    def test_general_b2c_and_niche_in_order_filtered_by_country(self):
        out = lib.suggest(NICHES, ACTS, ["school"], b2c=True, countries=["MD", "EU"])
        self.assertEqual([c["category"] for c in out["categories"]], ["civil", "consumer", "edu"])
        self.assertEqual(out["categories"][0]["acts"], ["md.cod.civil"])
        self.assertEqual(out["categories"][1]["acts"], ["eu.dir.2011-83"])

    def test_no_b2c_and_unknown_niche(self):
        out = lib.suggest(NICHES, ACTS, [], b2c=False, countries=["RO"])
        self.assertEqual([c["category"] for c in out["categories"]], ["civil"])
        with self.assertRaises(lib.WatchError):
            lib.suggest(NICHES, ACTS, ["bakery"], b2c=False, countries=["RO"])


class Watchlist(unittest.TestCase):
    def test_defaults_and_string_ids(self):
        wl = lib.validate_watchlist({"acts": ["ro.lege.287-2009"]})
        self.assertEqual(wl["acts"], [{"id": "ro.lege.287-2009"}])
        self.assertEqual(wl["settings"]["engines"], ["urllib"])

    def test_errors_name_the_field(self):
        bad = {"settings": {"countries": ["US"], "language": "de", "engines": ["magic"], "schedule": "daily"},
               "acts": [{"id": "bad id"}, {"id": "ro.lege.1-2020", "priority": "p9",
                                           "sources": [{"kind": "legis_md"}]}, {"id": "ro.lege.1-2020"}]}
        with self.assertRaises(lib.WatchError) as e:
            lib.validate_watchlist(bad)
        for word in ("countries", "language", "engines", "schedule", "acts[0]", "priority", "doc_id", "duplicate"):
            self.assertIn(word, str(e.exception))

    def test_command_engine_needs_url_placeholder(self):
        with self.assertRaises(lib.WatchError):
            lib.validate_watchlist({"settings": {"engines": ["command"], "fetch_command": "my-reader"}})

    def test_yaml_round_trip_and_bad_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "watchlist.yaml"
            p.write_text(lib.dump_watchlist({"schema_version": 1, "acts": [{"id": "md.cod.civil"}]}), encoding="utf-8")
            self.assertEqual(lib.load_watchlist(p)["acts"], [{"id": "md.cod.civil"}])
            p.write_text("acts: [", encoding="utf-8")
            with self.assertRaises(lib.WatchError):
                lib.load_watchlist(p)
            with self.assertRaises(lib.WatchError):
                lib.load_watchlist(Path(tmp) / "none.yaml")

    def test_template_is_valid(self):
        wl = lib.load_watchlist(SKILL / "templates" / "watchlist.yaml")
        self.assertEqual(wl["settings"]["engines"], ["urllib", "host"])

    def test_resolve_merges_catalog_entry_and_baseline(self):
        wl = lib.validate_watchlist({"acts": [{"id": "md.cod.civil", "priority": "p1"},
                                              {"id": "md.lege.1-2026", "title": "Own", "jurisdiction": "MD"}]})
        state = {"acts": {"md.cod.civil": {"current": {"label": "v1"}, "next": None}}}
        acts = lib.resolve_acts(wl, ACTS, state)
        self.assertEqual((acts[0]["title"], acts[0]["priority"], acts[0]["current"]), ("md.cod.civil", "p1", {"label": "v1"}))
        self.assertEqual(acts[1]["priority"], "p2")
        with self.assertRaises(lib.WatchError):
            lib.resolve_acts(lib.validate_watchlist({"acts": ["md.lege.2-2026"]}), ACTS, state)

    def test_select(self):
        acts = [{"id": "a.b.c", "priority": "p1"}, {"id": "a.b.d", "priority": "p2"}]
        self.assertEqual(len(lib.select(acts, "all")), 2)
        self.assertEqual([a["id"] for a in lib.select(acts, "p2")], ["a.b.d"])
        self.assertEqual([a["id"] for a in lib.select(acts, "a.b.c")], ["a.b.c"])
        with self.assertRaises(lib.WatchError):
            lib.select(acts, "x.y.z")


class Snapshots(unittest.TestCase):
    def test_new_file_only_when_text_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            prof = Path(tmp)
            a = lib.save_snapshot(prof, "md.cod.civil", "text one", "1" * 64, "2026-11-01")
            b = lib.save_snapshot(prof, "md.cod.civil", "text one", "1" * 64, "2026-11-04")
            c = lib.save_snapshot(prof, "md.cod.civil", "text two", "2" * 64, "2026-11-04")
            self.assertEqual(a, b)
            self.assertNotEqual(a, c)
            self.assertIsNone(lib.save_snapshot(prof, "md.cod.civil", "", None, "2026-11-04"))


CONTRACT = """CONTRACT DE PRESTĂRI SERVICII
1. Obiectul contractului
1.1. Prestatorul prestează servicii conform Codului civil.
5. Date cu caracter personal
5.2. Părțile prelucrează datele conform Regulamentului (UE) 2016/679 și Legii nr. 190/2018, art. 5.
7.1. Penalități conform OUG nr. 13/2011 și H.G. nr. 905/2017.
8. Litigiile se soluționează potrivit Codului de procedură civilă.
"""


class ClauseScan(unittest.TestCase):
    def scan(self, text=CONTRACT, jur="RO", suffix=".txt"):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / f"services{suffix}"
            p.write_text(text, encoding="utf-8")
            return clauses.scan(p, jur)

    def test_citations_by_clause(self):
        ix = self.scan()
        rows = {c["clause"]: [a["id"] for a in c["acts"]] for c in ix["clauses"]}
        self.assertEqual(rows["1.1"], ["ro.cod.civil"])
        self.assertEqual(rows["5.2"], ["ro.lege.190-2018", "eu.reg.2016-679"])
        self.assertEqual(rows["7.1"], ["ro.oug.13-2011", "ro.hg.905-2017"])
        self.assertEqual(rows["8"], ["ro.cod.procedura-civila"])
        prov = {a["id"]: a["provision"] for a in ix["clauses"][1]["acts"]}
        self.assertEqual(prov["ro.lege.190-2018"], "art. 5")
        self.assertEqual(clauses.validate(ix), [])

    def test_moldovan_contract_and_docx(self):
        import docx
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "md.docx"
            d = docx.Document()
            d.add_paragraph("3.1. Conform Legii nr. 133/2011 și Codului civil.")
            d.save(p)
            ix = clauses.scan(p, "MD")
        self.assertEqual([a["id"] for a in ix["clauses"][0]["acts"]], ["md.lege.133-2011", "md.cod.civil"])

    def test_bad_inputs(self):
        with self.assertRaises(lib.WatchError):
            self.scan(jur="EU")
        with self.assertRaises(lib.WatchError):
            self.scan(suffix=".pdf")

    def test_validate_and_save(self):
        ix = self.scan()
        ix["clauses"][0]["source"] = "guess"
        ix["clauses"][1]["acts"].append({"id": "us.code.1"})
        errs = clauses.validate(ix, known_ids={"ro.cod.civil"})
        self.assertTrue(any("source" in e for e in errs))
        self.assertTrue(any("bad act id" in e for e in errs))
        self.assertTrue(any("neither in the catalog" in e for e in errs))
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(lib.WatchError):
            clauses.save(Path(tmp), ix)
        with tempfile.TemporaryDirectory() as tmp:
            good = self.scan()
            clauses.save(Path(tmp), good)
            with self.assertRaises(lib.WatchError):
                clauses.save(Path(tmp), good)
            clauses.save(Path(tmp), good, force=True)


class Engines(unittest.TestCase):
    def test_challenge_detection(self):
        self.assertIsNotNone(F.detect_challenge(200, "Just a moment...", "", "x"))
        self.assertIsNotNone(F.detect_challenge(403, "", "", "x" * 2000))
        self.assertIsNotNone(F.detect_challenge(200, "", "<div class='g-recaptcha'>", "short"))
        self.assertIsNone(F.detect_challenge(200, "Lege", "<p>text</p>", "x" * 2000))

    def test_command_engine_passes_only_the_quoted_url(self):
        seen = {}

        def run(cmd, **kw):
            seen.update(cmd=cmd, env=kw.get("env"))
            return mock.Mock(returncode=0, stdout="# Legea nr. 1/2020\n\ntext", stderr="secret-ish")
        f = F.CommandFetcher("my-reader --url {url}", run=run, pause_range=(0, 0))
        url = "https://example.org/a?b=1&c=2"
        r = f.get(url)
        if os.name == "nt":   # cmd.exe: the URL travels in a variable (fetchers.command_line)
            self.assertEqual(seen["cmd"], 'my-reader --url "%LEGAL_WATCH_URL%"')
            self.assertEqual(seen["env"][F.URL_ENV], url)
        else:
            self.assertEqual(seen["cmd"], "my-reader --url 'https://example.org/a?b=1&c=2'")
            self.assertIsNone(seen["env"])
        self.assertEqual((r.via, r.markdown.startswith("# Legea"), r.error), ("command", True, None))
        bad = F.CommandFetcher("x {url}", run=lambda c, **k: mock.Mock(returncode=3, stdout="", stderr="token=1"),
                               pause_range=(0, 0)).get("https://example.org")
        self.assertNotIn("token", bad.error)
        with self.assertRaises(F.FetchConfigError):
            F.CommandFetcher("no placeholder")

    def test_chain_falls_through_and_names_the_engine(self):
        blocked = F.FixtureFetcher({"u": F.fixture_result("u", "<title>Just a moment</title>", status=403)})
        ok = F.FixtureFetcher({"u": F.fixture_result("u", "<title>Lege</title><p>" + "x" * 2100 + "</p>",
                                                     via="playwright")})
        r = F.ChainFetcher([blocked, ok]).get("u")
        self.assertEqual(r.via, "playwright")
        self.assertTrue(any("engine failed" in n for n in r.notes))
        with self.assertRaises(F.FetchConfigError):
            F.ChainFetcher([])

    def test_urllib_engine_maps_errors(self):
        import urllib.error

        def opener(req, timeout):
            raise urllib.error.URLError("down")
        r = F.UrllibFetcher(opener=opener, pause_range=(0, 0)).get("https://example.org")
        self.assertIn("URLError", r.error)

        class Resp:
            status = 200
            headers = mock.Mock(get_content_charset=lambda: "utf-8")
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b"<title>Lege</title><p>text</p>"
            def geturl(self): return "https://example.org/x"
        r = F.UrllibFetcher(opener=lambda req, timeout: Resp(), pause_range=(0, 0)).get("https://example.org")
        self.assertEqual((r.status, r.title, r.final_url), (200, "Lege", "https://example.org/x"))

    def test_build_chain(self):
        with self.assertRaises(F.FetchConfigError):
            F.build_chain(["command"])
        with self.assertRaises(F.FetchConfigError):
            F.build_chain(["playwright"])
        with self.assertRaises(F.FetchConfigError):
            F.build_chain(["fax"])
        self.assertEqual(len(F.build_chain(["urllib", "command"], command="x {url}").fetchers), 2)
        self.assertIn("host", F.HostOnly().get("u").error)


class Schedule(unittest.TestCase):
    def test_plans(self):
        prof = Path("/tmp/profile-x")
        self.assertIn("legal_watch.py", schedule.plan(prof, "launchd")["command"])
        self.assertTrue(schedule.plan(prof, "cron")["line"].startswith("0 9 * * 1 "))
        self.assertIn("legal-watch", schedule.plan(prof, "claude-schedule")["prompt"])
        with self.assertRaises(lib.WatchError):
            schedule.plan(prof, "at")

    def test_install_and_remove_in_a_fake_home(self):
        calls = []
        run = lambda cmd, **kw: calls.append(cmd) or mock.Mock(returncode=0, stderr="")  # noqa: E731
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(schedule.sys, "platform", "darwin"):
            out = schedule.install(Path(tmp) / "profile", run=run, home=Path(tmp))
            plist = Path(out["installed"])
            self.assertIn(b"com.legal-engine.watch", plist.read_bytes())
            self.assertEqual(schedule.remove(run=run, home=Path(tmp))["removed"], str(plist))
            self.assertIsNone(schedule.remove(run=run, home=Path(tmp))["removed"])
        self.assertEqual(calls[1][:2], ["launchctl", "load"])

    def test_install_refuses_elsewhere(self):
        with mock.patch.object(schedule.sys, "platform", "linux"), self.assertRaises(lib.WatchError):
            schedule.install(Path("/tmp/p"))


if __name__ == "__main__":
    unittest.main()
