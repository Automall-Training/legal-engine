"""Consistency of the consumer module: checkpoints, law map and the module-data template."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TEXT = (SKILL / "SKILL.md").read_text(encoding="utf-8")
CHECKPOINTS = (SKILL / "references" / "checkpoints.md").read_text(encoding="utf-8")
LAW_MAP = (SKILL / "references" / "law-map.md").read_text(encoding="utf-8")
TERMS = (SKILL / "references" / "terms-structure.md").read_text(encoding="utf-8")
TEMPLATE = json.loads((SKILL / "templates" / "module-data.json").read_text(encoding="utf-8"))


class Checkpoints(unittest.TestCase):
    def test_ids_are_consecutive(self):
        ids = re.findall(r"^\| (C\d+) \|", CHECKPOINTS, flags=re.M)
        self.assertEqual(ids, [f"C{i}" for i in range(1, len(ids) + 1)])
        self.assertGreaterEqual(len(ids), 12)

    def test_template_statuses_match_the_reference(self):
        statuses = TEMPLATE["module_data"]["checkpoints"][0]["status"].split(" | ")
        for status in statuses:
            with self.subTest(status=status):
                self.assertIn(f"**{status.replace('-', ' ')}**", " ".join(CHECKPOINTS.split("|")[0].split()))

    def test_every_ro_act_in_a_checkpoint_is_in_the_law_map(self):
        cited = set(re.findall(r"(OUG \d+/\d{4}|OG \d+/\d{4}|Law \d+/\d{4})", CHECKPOINTS))
        for act in cited:
            with self.subTest(act=act):
                self.assertIn(act, LAW_MAP)

    def test_moldova_never_copied_from_romania(self):
        moldova = CHECKPOINTS.split("## Moldova")[1].split("## ")[0]
        self.assertIn("never", moldova)
        self.assertIn("not verified", moldova)


class LawMap(unittest.TestCase):
    def test_act_ids_are_well_formed(self):
        for act in re.findall(r"^\| `([^`]+)` \|", LAW_MAP, flags=re.M):
            with self.subTest(act=act):
                self.assertRegex(act, r"^(eu|md|ro)\.[a-z]+\.[0-9a-z]+(-[0-9]+)?$")

    def test_three_jurisdictions(self):
        self.assertEqual(re.findall(r"^## (.+)$", LAW_MAP, flags=re.M), ["European Union", "Romania", "Moldova"])


class TermsStructure(unittest.TestCase):
    """The module is generic: every product type of the template has a block, and blocks cite real checkpoints."""

    BLOCK_FOR = {"goods": "Goods (", "goods-digital": "Goods with digital", "service": "Service (",
                 "digital-content": "Digital content", "digital-service": "Digital content or service",
                 "subscription": "Subscription", "course-or-event": "Course, event", "bundle": "Bundle"}

    def test_every_product_type_has_a_block(self):
        products = TEMPLATE["module_data"]["products"][0].split(" | ")
        self.assertEqual(set(products), set(self.BLOCK_FOR))
        for product, label in self.BLOCK_FOR.items():
            with self.subTest(product=product):
                self.assertIn(f"| {label}", TERMS)

    def test_cited_checkpoints_exist(self):
        known = set(re.findall(r"^\| (C\d+) \|", CHECKPOINTS, flags=re.M))
        for cid in set(re.findall(r"\bC\d+\b", TERMS)):
            with self.subTest(checkpoint=cid):
                self.assertIn(cid, known)

    def test_route_has_a_configuration_step(self):
        self.assertIn("**Configuration**", TEXT)
        self.assertIn("§15", TEXT)


class Scope(unittest.TestCase):
    def test_privacy_part_is_handed_over(self):
        self.assertIn("`legal-privacy`", TEXT)
        self.assertIn("legal-privacy", CHECKPOINTS)


if __name__ == "__main__":
    unittest.main()
