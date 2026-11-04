"""Consistency of the privacy module: procedures, documents table, law map and the module-data template."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
MODELS = SKILL.parent / "legal-contracts" / "references" / "models"
TEXT = (SKILL / "SKILL.md").read_text(encoding="utf-8")
PROCEDURES = (SKILL / "references" / "procedures.md").read_text(encoding="utf-8")
DOCUMENTS = (SKILL / "references" / "documents.md").read_text(encoding="utf-8")
LAW_MAP = (SKILL / "references" / "law-map.md").read_text(encoding="utf-8")
TEMPLATE = json.loads((SKILL / "templates" / "module-data.json").read_text(encoding="utf-8"))

STEPS = ("new website", "processor or dpa", "transfer abroad", "dpia screening", "data subject request", "data breach")


class Procedures(unittest.TestCase):
    def test_six_procedures_in_order(self):
        headings = re.findall(r"^## \d\. (.+)$", PROCEDURES, flags=re.M)
        self.assertEqual([h.lower()[:len(s)] for h, s in zip(headings, STEPS)], list(STEPS))
        self.assertEqual(len(headings), len(STEPS))

    def test_every_procedure_ends_with_an_outcome(self):
        for section in re.split(r"^## \d\. ", PROCEDURES, flags=re.M)[1:]:
            with self.subTest(section=section.splitlines()[0]):
                self.assertIn("**Outcome:**", section)

    def test_template_names_every_procedure(self):
        named = TEMPLATE["module_data"]["procedure"].split(" | ")
        self.assertEqual(named[:6], ["channel", "processor", "transfer", "dpia", "request", "breach"])

    def test_breach_goes_first_and_works_when_off(self):
        # why: the 72-hour clock runs whatever the switch says; the module must not stall on a setup question.
        before = TEXT.split("## Route")[0]
        self.assertLess(before.index("**Breach first.**"), before.index("**Module on?**"))
        self.assertIn("72 hours", PROCEDURES.split("## 6.")[1].split("\n\n")[1])


class Documents(unittest.TestCase):
    def test_model_cards_exist(self):
        cards = set(re.findall(r"`(\d\d-[a-z-]+\.ro\.md)`", DOCUMENTS))
        self.assertEqual({c[:2] for c in cards}, {"06", "07", "08", "09", "10"})
        for card in cards:
            with self.subTest(card=card):
                self.assertTrue((MODELS / card).is_file())

    def test_template_documents_have_a_row(self):
        kinds = TEMPLATE["module_data"]["documents"][0].split(" | ")
        rows = [line for line in DOCUMENTS.splitlines() if line.startswith("| ") and not line.startswith("| Document")]
        self.assertGreaterEqual(len(rows) - 1, len(kinds) - 1)  # why: the separator row is not a document


class LawMap(unittest.TestCase):
    def test_act_ids_are_well_formed(self):
        for act in re.findall(r"^\| `([^`]+)` \|", LAW_MAP, flags=re.M):
            with self.subTest(act=act):
                self.assertRegex(act, r"^(eu|md|ro)\.[a-z]+\.[0-9a-z]+(-[0-9]+)?$")

    def test_old_moldovan_law_only_as_a_trap(self):
        for line in LAW_MAP.splitlines():
            if "133/2011" in line:
                self.assertRegex(line, r"repeals|never|old")


if __name__ == "__main__":
    unittest.main()
