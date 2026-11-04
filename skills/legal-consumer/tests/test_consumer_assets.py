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


class Scope(unittest.TestCase):
    def test_privacy_part_is_handed_over(self):
        self.assertIn("`legal-privacy`", TEXT)
        self.assertIn("legal-privacy", CHECKPOINTS)


if __name__ == "__main__":
    unittest.main()
