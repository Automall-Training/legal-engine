"""Consistency of the trademark module: procedures, law map, templates and the enabling rules."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
REFS = SKILL / "references"
TEXT = (SKILL / "SKILL.md").read_text(encoding="utf-8")
PROCEDURES = (REFS / "procedures.md").read_text(encoding="utf-8")
LAW_MAP = (REFS / "law-map.md").read_text(encoding="utf-8")
STRATEGY = (REFS / "filing-strategy.md").read_text(encoding="utf-8")
TEMPLATE = json.loads((SKILL / "templates" / "module-data.json").read_text(encoding="utf-8"))
RULES = json.loads((SKILL / "assets" / "deadline-rules.json").read_text(encoding="utf-8"))["rules"]

PROCEDURE_IDS = ["clearance", "filing", "portfolio", "office-letter", "opposition", "infringement",
                 "claim-received", "licence"]


class Procedures(unittest.TestCase):
    def test_eight_procedures_in_order_each_with_an_outcome(self):
        heads = re.findall(r"^## (\d+)\. ", PROCEDURES, flags=re.M)
        self.assertEqual(heads, [str(i) for i in range(1, 9)])
        for block in re.split(r"^## \d+\. ", PROCEDURES, flags=re.M)[1:]:
            self.assertIn("**Outcome:**", block)

    def test_template_names_every_procedure(self):
        self.assertEqual(TEMPLATE["module_data"]["procedure"].split(" | "), PROCEDURE_IDS)

    def test_route_lists_the_same_procedures(self):
        route = TEXT.split("## Route")[1]
        for i in range(1, 9):
            self.assertIn(f"{i} ", route)

    def test_verdict_scale_is_the_norms_scale(self):
        verdicts = TEMPLATE["module_data"]["options"][0]["verdict"].split(" | ")
        self.assertEqual(verdicts, ["se poate", "se poate cu condiție", "risc", "interzis"])


class Enabling(unittest.TestCase):
    """The module looks for the lawful, cheapest way; it never promises what no search can prove."""

    def test_configuration_step_and_norms_section(self):
        self.assertIn("**Configuration**", TEXT)
        self.assertIn("§15", TEXT)
        self.assertIn("§15", STRATEGY)

    def test_never_promises_availability(self):
        for name, text in (("SKILL.md", TEXT), ("procedures.md", PROCEDURES)):
            with self.subTest(file=name):
                self.assertIn('Never', text)
                self.assertRegex(text, r'"available"')

    def test_ways_around_a_conflict_before_dropping_a_name(self):
        clearance = PROCEDURES.split("## 2.")[0]
        for lever in ("coexistence", "non-use", "narrower specification"):
            self.assertIn(lever, clearance)

    def test_enforcement_ladder_has_five_rungs(self):
        rungs = re.findall(r"^\| ([0-4]) \|", PROCEDURES, flags=re.M)
        self.assertEqual(rungs, ["0", "1", "2", "3", "4"])
        self.assertEqual(TEMPLATE["module_data"]["rung"].split(" | "), rungs)


class LawMap(unittest.TestCase):
    def test_act_ids_are_well_formed(self):
        for act in re.findall(r"^\| `([^`]+)` \|", LAW_MAP, flags=re.M):
            with self.subTest(act=act):
                self.assertRegex(act, r"^(eu|md|ro|int)\.[a-z]+\.[0-9a-z]+(-[0-9]+)?$")

    def test_sections(self):
        self.assertEqual(re.findall(r"^## (.+)$", LAW_MAP, flags=re.M),
                         ["International", "European Union", "Romania", "Moldova", "Known traps"])

    def test_every_office_of_the_rules_has_its_jurisdiction(self):
        for office in {r["office"] for r in RULES} - {"*"}:
            with self.subTest(office=office):
                self.assertIn(office, LAW_MAP)

    def test_moldova_never_copied(self):
        moldova = LAW_MAP.split("## Moldova")[1].split("## ")[0]
        self.assertIn("not verified", moldova)
        self.assertIn("no Romanian or EU rule is presented as Moldovan", moldova)


class Portfolio(unittest.TestCase):
    def test_portfolio_lives_in_the_profile(self):
        self.assertIn("<profile>/trademarks/portfolio.json", TEXT)
        self.assertIn("<profile>/trademarks/portfolio.json", PROCEDURES)


if __name__ == "__main__":
    unittest.main()
