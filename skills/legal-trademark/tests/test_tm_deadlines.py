"""tm_deadlines.py: month arithmetic, rule loading, portfolio validation and the CLI."""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))
import tm_deadlines as tm  # noqa: E402

D = dt.date


def mark(**over):
    base = {"id": "m1", "name": "EXAMPLO", "office": "EUIPO", "status": "registered"}
    base.update(over)
    return base


class AddMonths(unittest.TestCase):
    def test_same_day_number(self):
        self.assertEqual(tm.add_months(D(2026, 1, 15), 3), D(2026, 4, 15))

    def test_end_of_month_when_the_day_is_missing(self):
        self.assertEqual(tm.add_months(D(2026, 1, 31), 1), D(2026, 2, 28))
        self.assertEqual(tm.add_months(D(2027, 11, 30), 3), D(2028, 2, 29))

    def test_negative_and_across_years(self):
        self.assertEqual(tm.add_months(D(2026, 3, 31), -6), D(2025, 9, 30))
        self.assertEqual(tm.add_months(D(2026, 12, 1), 120), D(2036, 12, 1))


class Rules(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def write(self, data) -> Path:
        path = self.tmp / "rules.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_shipped_rules_load_and_are_never_marked_verified(self):
        rules = tm.load_rules()
        self.assertEqual(len({r["id"] for r in rules}), len(rules))
        for rule in rules:
            with self.subTest(rule=rule["id"]):
                self.assertIn(rule["status"], {"reported", "not-read"})
                self.assertTrue(rule["basis"])

    def test_bad_rules_are_named(self):
        cases = [
            ({"schema_version": 1, "rules": []}, "non-empty"),
            ({"schema_version": 1, "rules": [{"id": "x", "office": "EUIPO", "event": "nope", "months": 1}]}, "event"),
            ({"schema_version": 1, "rules": [{"id": "x", "office": "XX", "event": "filed_on", "months": 1}]}, "office"),
            ({"schema_version": 1, "rules": [{"id": "x", "office": "*", "event": "filed_on"}]}, "exactly one"),
            ({"schema_version": 2, "rules": []}, "schema_version"),
        ]
        for data, word in cases:
            with self.subTest(word=word), self.assertRaisesRegex(tm.TrademarkInputError, word):
                tm.load_rules(self.write(data))

    def test_missing_and_broken_files(self):
        with self.assertRaisesRegex(tm.TrademarkInputError, "not found"):
            tm.load_json(self.tmp / "none.json")
        bad = self.tmp / "bad.json"
        bad.write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(tm.TrademarkInputError, "not valid JSON"):
            tm.load_json(bad)


class Portfolio(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.rules = tm.load_rules()

    def write(self, marks) -> Path:
        path = self.tmp / "portfolio.json"
        path.write_text(json.dumps({"schema_version": 1, "marks": marks}), encoding="utf-8")
        return path

    def rows(self, marks, today=D(2026, 11, 4), **kw):
        return tm.portfolio_deadlines(self.write(marks), today, kw.get("horizon"), kw.get("past", False), self.rules)

    def test_template_portfolio_is_valid(self):
        rows = tm.portfolio_deadlines(SKILL / "templates" / "portfolio.json", D(2026, 11, 4), None, False)
        self.assertTrue(rows)
        self.assertEqual(rows, sorted(rows, key=lambda r: r["date"]))
        for row in rows:
            self.assertIn("not verified", row["note"])

    def test_osim_opposition_counts_from_the_admission(self):
        rows = self.rows([mark(office="OSIM", status="admitted", admission_published_on="2026-10-01")])
        self.assertEqual({r["rule"]: r["date"] for r in rows}["osim.opposition"], "2026-12-01")

    def test_urgent_under_fourteen_days(self):
        rows = self.rows([mark(office="OSIM", status="admitted", closure_notified_on="2026-10-10")])
        fee = next(r for r in rows if r["rule"] == "osim.certificate-fee")
        self.assertEqual((fee["date"], fee["days_left"], fee["urgent"]), ("2026-11-09", 5, True))

    def test_recorded_expiry_beats_the_computed_term(self):
        rows = self.rows([mark(filed_on="2020-01-10", expires_on="2030-02-01")], horizon=99999)
        ids = {r["rule"] for r in rows}
        self.assertNotIn("euipo.term", ids)
        self.assertIn("renewal.opens", ids)
        self.assertEqual({r["rule"]: r["date"] for r in rows}["renewal.opens"], "2029-08-01")

    def test_grace_only_after_expiry(self):
        before = {r["rule"] for r in self.rows([mark(expires_on="2027-01-01")])}
        after = {r["rule"] for r in self.rows([mark(expires_on="2026-10-01")])}
        self.assertNotIn("renewal.grace-ends", before)
        self.assertIn("renewal.grace-ends", after)

    def test_inactive_marks_and_other_offices_give_nothing(self):
        self.assertEqual(self.rows([mark(status="refused", filed_on="2026-10-01")]), [])
        rows = self.rows([mark(office="AGEPI", status="filed", published_on="2026-10-01")])
        self.assertEqual({r["rule"] for r in rows}, {"agepi.opposition"})
        self.assertEqual(rows[0]["status"], "not-read")

    def test_past_and_horizon_filters(self):
        marks = [mark(filed_on="2026-01-01", registered_on="2026-09-01")]
        self.assertNotIn("paris.priority", {r["rule"] for r in self.rows(marks)})
        self.assertIn("paris.priority", {r["rule"] for r in self.rows(marks, past=True)})
        self.assertEqual(self.rows(marks, horizon=30), [])

    def test_invalid_marks_are_named(self):
        cases = [
            (["x"], "must be an object"),
            ([{"id": "a", "office": "EUIPO", "status": "filed"}], "'name' are required"),
            ([mark(office="USPTO")], "office must be"),
            ([mark(status="alive")], "status must be"),
            ([mark(filed_on="10.01.2026")], "filed_on"),
            ([mark(filed_on=20260110)], "expected a date"),
            ([mark(), mark()], "appears twice"),
        ]
        for marks, word in cases:
            with self.subTest(word=word), self.assertRaisesRegex(tm.TrademarkInputError, word):
                self.rows(marks)

    def test_marks_must_be_a_list(self):
        path = self.tmp / "p.json"
        path.write_text(json.dumps({"schema_version": 1, "marks": {}}), encoding="utf-8")
        with self.assertRaisesRegex(tm.TrademarkInputError, "must be a list"):
            tm.load_portfolio(path)


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = tm.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_rules(self):
        code, out, _ = self.run_cli("rules")
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out))

    def test_compute(self):
        code, out, _ = self.run_cli("compute", "--rule", "euipo.opposition", "--date", "2026-11-30")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["date"], "2027-02-28")
        self.assertEqual(json.loads(out)["status"], "reported")

    def test_compute_days_rule(self):
        code, out, _ = self.run_cli("compute", "--rule", "osim.certificate-fee", "--date", "2026-12-15")
        self.assertEqual((code, json.loads(out)["date"]), (0, "2027-01-14"))

    def test_input_errors_exit_2(self):
        for args in (("compute", "--rule", "nope", "--date", "2026-01-01"),
                     ("compute", "--rule", "euipo.opposition", "--date", "bad"),
                     ("portfolio", "--file", "/nonexistent/portfolio.json")):
            with self.subTest(args=args):
                code, _, err = self.run_cli(*args)
                self.assertEqual(code, 2)
                self.assertIn("input error", err)

    def test_portfolio(self):
        code, out, _ = self.run_cli("portfolio", "--file", str(SKILL / "templates" / "portfolio.json"),
                                    "--today", "2026-11-04", "--horizon-days", "60", "--all")
        self.assertEqual(code, 0)
        self.assertTrue(all(r["days_left"] <= 60 for r in json.loads(out)))

    def test_portfolio_default_today(self):
        code, _, _ = self.run_cli("portfolio", "--file", str(SKILL / "templates" / "portfolio.json"))
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
