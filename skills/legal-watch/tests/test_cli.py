"""The command line end to end on a temporary profile, with the shipped catalog and no network (engine host)."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))
import legal_watch as cli  # noqa: E402
from watch import library as lib  # noqa: E402


def call(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.profile = Path(self.tmp.name)
        _, niches = lib.load_catalog()
        self.niche = next(iter(niches["niches"]))

    def tearDown(self):
        self.tmp.cleanup()

    def p(self, *argv):
        return call("--profile", str(self.profile), *argv)

    def test_catalog_and_suggest(self):
        code, out, _ = call("catalog", "niches")
        self.assertEqual(code, 0)
        self.assertIn(self.niche, json.loads(out))
        self.assertEqual(call("catalog", "categories")[0], 0)
        acts = json.loads(call("catalog", "acts", "--countries", "MD")[1])
        self.assertTrue(acts and all(a["jurisdiction"] == "MD" for a in acts))
        sug = json.loads(call("suggest", "--niches", self.niche, "--b2c", "--countries", "RO,EU")[1])
        self.assertTrue(sug["categories"])

    def test_init_show_run_digest_on_host_engine(self):
        code, out, _ = self.p("init", "--niches", self.niche, "--acts", "p1", "--countries", "RO",
                              "--engines", "host", "--language", "ro")
        self.assertEqual(code, 0, out)
        n = json.loads(out)["acts"]
        self.assertGreater(n, 0)
        self.assertEqual(self.p("init", "--niches", self.niche)[0], 2)  # never replaced silently
        show = json.loads(self.p("show")[1])
        self.assertEqual(len(show["acts"]), n)
        code, out, _ = self.p("run", "--today", "2026-11-04")
        self.assertEqual(code, 2)  # host only: nothing read, so never "no changes"
        self.assertTrue(out.startswith("INCOMPLETE"))
        code, out, _ = self.p("digest")
        self.assertIn("Neverificate", out)
        self.assertNotIn("Nicio modificare", out)

    def test_init_with_own_act_and_unknown_category(self):
        self.assertEqual(self.p("init", "--niches", self.niche, "--categories", "nope")[0], 2)
        code, out, _ = self.p("init", "--niches", self.niche, "--acts", "none", "--add", "eu.reg.2016-679")
        self.assertEqual((code, json.loads(out)["acts"]), (0, 1))

    def test_errors_are_short_messages(self):
        code, _, err = self.p("show")
        self.assertEqual(code, 2)
        self.assertIn("watchlist not found", err)
        self.assertEqual(self.p("digest")[0], 2)
        self.assertEqual(self.p("index", "scan")[0], 2)
        self.assertEqual(self.p("index", "clear")[0], 2)
        self.assertEqual(self.p("schedule", "install", "--kind", "cron")[0], 2)

    def test_index_commands(self):
        contract = self.profile / "contracts" / "services.txt"
        contract.parent.mkdir(parents=True)
        contract.write_text("4.1. Datele se prelucrează conform Regulamentului (UE) 2016/679.\n", encoding="utf-8")
        code, out, _ = self.p("index", "scan", str(contract), "--jurisdiction", "RO")
        self.assertEqual(json.loads(out)["clauses"][0]["acts"][0]["id"], "eu.reg.2016-679")
        self.assertEqual(self.p("index", "scan", str(contract), "--jurisdiction", "RO", "--write")[0], 0)
        self.assertEqual(self.p("index", "check")[0], 2)  # no watchlist yet: nothing can reach a clause
        self.p("init", "--niches", self.niche, "--acts", "md.cod.civil")
        code, out, _ = self.p("index", "check")
        self.assertEqual(code, 1)  # in the catalog but not watched: reported
        self.assertIn("eu.reg.2016-679", out)
        self.p("init", "--niches", self.niche, "--acts", "eu.reg.2016-679", "--force")
        code, out, _ = self.p("index", "check")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(self.p("index", "pending")[1]), [])
        self.assertEqual(self.p("index", "clear", "--contract", "services.txt", "--matter", "m1")[0], 2)

    def test_schedule_plan(self):
        code, out, _ = self.p("schedule", "plan", "--kind", "cron")   # cron asked for explicitly, on any system
        self.assertEqual(code, 0)
        # the schedule writes the resolved absolute path (Windows: long names instead of RUNNER~1; macOS: /private)
        self.assertIn(str(self.profile.resolve()), json.loads(out)["line"])


if __name__ == "__main__":
    unittest.main()
