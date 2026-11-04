"""Consistency of the employment module: procedures, law map, configuration, documents and the template."""

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
CONFIG = (REFS / "configuration.md").read_text(encoding="utf-8")
DOCUMENTS = (REFS / "documents.md").read_text(encoding="utf-8")
TEMPLATE = json.loads((SKILL / "templates" / "module-data.json").read_text(encoding="utf-8"))["module_data"]

PROCEDURE_IDS = ["hiring", "amendment", "ending", "internal-rules", "contractor-or-employee",
                 "inspection-or-claim", "cross-border"]


class Procedures(unittest.TestCase):
    def test_seven_procedures_in_order_each_with_an_outcome(self):
        self.assertEqual(re.findall(r"^## (\d+)\. ", PROCEDURES, flags=re.M), [str(i) for i in range(1, 8)])
        for block in re.split(r"^## \d+\. ", PROCEDURES, flags=re.M)[1:]:
            self.assertIn("**Outcome:**", block)

    def test_template_names_every_procedure(self):
        self.assertEqual(TEMPLATE["procedure"].split(" | "), PROCEDURE_IDS)

    def test_route_lists_the_procedures(self):
        route = TEXT.split("## Route")[1].split("## Rules")[0]
        for word in ("hiring", "amendment", "ending", "internal", "contractor", "inspection", "borders"):
            self.assertIn(word, route)


class Enabling(unittest.TestCase):
    """The module finds a lawful, cheap way to engage and end work; real limits are named, not invented."""

    def test_configuration_step_and_norms_section(self):
        self.assertIn("**Configuration**", TEXT)
        for text in (TEXT, CONFIG):
            self.assertIn("§15", text)

    def test_every_engagement_of_the_template_has_a_row(self):
        rows = {"indefinite": "indefinite", "fixed-term": "Fixed term", "part-time": "Part time",
                "telework": "telework", "civil-contract": "Civil contract", "agency": "agency",
                "day-labourer": "Day labourer"}
        self.assertEqual(set(TEMPLATE["engagement"].split(" | ")), set(rows))
        ways = CONFIG.split("## Ways to engage")[1].split("## ")[0]
        for key, label in rows.items():
            with self.subTest(engagement=key):
                self.assertIn(label, ways)

    def test_ending_routes_start_with_the_agreement(self):
        ending = CONFIG.split("## Ending")[1].split("## ")[0]
        first = re.findall(r"^\| ([A-Z][^|]+?) \|", ending, flags=re.M)
        self.assertEqual(first[1], "Agreement of the parties")  # first row after the header
        self.assertIn("agreement is offered before a dismissal", PROCEDURES)

    def test_optional_documents_are_offered_as_optional(self):
        self.assertIn("optional", DOCUMENTS)
        self.assertIn("*may*", TEXT)

    def test_verdict_scale_is_the_norms_scale(self):
        self.assertEqual(TEMPLATE["options"][0]["verdict"].split(" | "),
                         ["se poate", "se poate cu condiție", "risc", "interzis"])


class LawMap(unittest.TestCase):
    def test_act_ids_are_well_formed(self):
        for act in re.findall(r"^\| `([^`]+)` \|", LAW_MAP, flags=re.M):
            with self.subTest(act=act):
                self.assertRegex(act, r"^(eu|md|ro)\.[a-z]+\.[0-9a-z]+(-[0-9]+)?$")

    def test_sections(self):
        self.assertEqual(re.findall(r"^## (.+)$", LAW_MAP, flags=re.M),
                         ["European Union", "Romania", "Moldova", "Cross-border", "Known traps"])

    def test_moldova_never_copied(self):
        moldova = LAW_MAP.split("## Moldova")[1].split("## ")[0]
        self.assertIn("no\nRomanian rule is presented as Moldovan", moldova)

    def test_amounts_never_from_memory(self):
        self.assertIn("never given from memory", LAW_MAP)
        self.assertIn("never from memory", TEXT)

    def test_every_ro_and_md_act_in_documents_is_mapped(self):
        for law in set(re.findall(r"Law \d+/\d{4}", DOCUMENTS)):
            with self.subTest(law=law):
                number, year = law.split()[1].split("/")
                self.assertIn(f".{number}-{year}`", LAW_MAP)


class Privacy(unittest.TestCase):
    def test_staff_data_handed_to_privacy(self):
        self.assertIn("`legal-privacy`", TEXT)
        self.assertIn("the role, not the person", " ".join(PROCEDURES.split()))


if __name__ == "__main__":
    unittest.main()
