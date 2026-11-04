"""Consistency of the shipped catalog: niches -> law categories -> acts (Moldova, Romania, EU).

No network: the catalog only names acts and where to find them. Whether an act is in force is checked on
the official portal on the task date, never here.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SKILLS = SKILL.parent
CATALOG = SKILL / "assets" / "catalog"
ACTS_DOC = json.loads((CATALOG / "acts.json").read_text(encoding="utf-8"))
NICHES_DOC = json.loads((CATALOG / "niches.json").read_text(encoding="utf-8"))
ACTS = {a["id"]: a for a in ACTS_DOC["acts"]}

# <md|ro|eu>.<kind>.<number>-<year>, or <md|ro>.cod.<name> for codes the engine names by their short name.
ACT_ID = re.compile(r"^(?:(?:md|ro|eu)\.[a-z]+\.\d+-\d{1,4}|(?:md|ro)\.cod\.[a-z][a-z-]*)$")
# Any backticked token that looks like an act id in a law map (looser, so a malformed id is caught too).
CITED = re.compile(r"`((?:md|ro|eu)\.[a-z]+\.[a-z0-9-]+)`")
CELEX = re.compile(r"^3\d{4}[A-Z]\d{4}$")
DOC_ID = re.compile(r"^\d+$")
JURISDICTIONS = {"MD", "RO", "EU"}
STATUSES = {"verified", "reported"}
PRIORITIES = {"p1", "p2", "p3"}
SOURCE_KEY = {"legis_md": "doc_id", "just_ro": "doc_id", "eurlex": "celex"}
SOURCE_JURISDICTION = {"legis_md": "MD", "just_ro": "RO", "eurlex": "EU"}
LANGS = {"en", "ro", "ru"}

# Ids cited in a law map that are deliberately not catalog acts. Empty today: every cited id is a real act.
# Add an id here only with a comment saying why (for example a placeholder in an example sentence).
NOT_ACTS: set[str] = set()


def iso(value: str) -> bool:
    try:
        dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True


class Acts(unittest.TestCase):
    def test_top_level(self):
        self.assertEqual(ACTS_DOC["schema_version"], 1)
        self.assertTrue(iso(ACTS_DOC["checked_on"]))
        self.assertTrue(any("legis.md" in n and "version" in n for n in ACTS_DOC["notes"]),
                        "the notes must say a legis.md doc_id is one version, not the act")

    def test_ids_well_formed_and_unique(self):
        ids = [a["id"] for a in ACTS_DOC["acts"]]
        self.assertEqual(len(ids), len(set(ids)), "duplicate act ids")
        for i in ids:
            self.assertRegex(i, ACT_ID)

    def test_fields(self):
        for a in ACTS_DOC["acts"]:
            with self.subTest(act=a["id"]):
                self.assertEqual(a["jurisdiction"], a["id"][:2].upper())
                self.assertIn(a["jurisdiction"], JURISDICTIONS)
                self.assertTrue(a["title"].strip())
                self.assertTrue(a["kind"].strip())
                self.assertRegex(a["number"], r"^\d+$")
                self.assertRegex(a["year"], r"^(19|20)\d{2}$")
                self.assertIn(a["priority"], PRIORITIES)
                self.assertIn(a["status"], STATUSES)
                self.assertTrue(iso(a["checked_on"]))
                self.assertLessEqual(a["checked_on"], ACTS_DOC["checked_on"])
                self.assertTrue(a["official_url"].startswith("https://"))
                self.assertIn("note", a)
                if ".cod." in a["id"]:
                    self.assertEqual(a["kind"], "code")
                    self.assertEqual(a["id"].split(".", 2)[2], a["code"])
                if "code" in a:
                    self.assertEqual(a["kind"], "code")
                    self.assertRegex(a["code"], r"^[a-z][a-z-]*$")
                if a["id"].count(".") == 2 and ".cod." not in a["id"]:
                    # why: ids follow the official citation, "593-2008" or "2016-679" or "93-13"
                    parts = set(a["id"].split(".")[2].split("-"))
                    self.assertIn(parts, ({a["number"], a["year"]}, {a["number"], a["year"][2:]}))

    def test_sources(self):
        for a in ACTS_DOC["acts"]:
            with self.subTest(act=a["id"]):
                for s in a["sources"]:
                    self.assertIn(s["kind"], SOURCE_KEY)
                    self.assertEqual(SOURCE_JURISDICTION[s["kind"]], a["jurisdiction"])
                    key = SOURCE_KEY[s["kind"]]
                    self.assertEqual(set(s), {"kind", key})
                    if key == "celex":
                        self.assertRegex(s["celex"], CELEX)
                        self.assertIn(s["celex"], a["official_url"])
                    else:
                        self.assertRegex(s["doc_id"], DOC_ID)
                        self.assertIn(s["doc_id"], a["official_url"])

    def test_no_source_means_a_note_and_no_verified(self):
        # why: a missing doc_id must never look like a checked one
        for a in ACTS_DOC["acts"]:
            if not a["sources"]:
                with self.subTest(act=a["id"]):
                    self.assertEqual(a["status"], "reported")
                    self.assertIn("first run", a["note"] or "")

    def test_eu_acts_have_celex(self):
        for a in ACTS_DOC["acts"]:
            if a["jurisdiction"] == "EU":
                self.assertTrue(any(s["kind"] == "eurlex" for s in a["sources"]), a["id"])


class Niches(unittest.TestCase):
    CATS = NICHES_DOC["categories"]

    def test_top_level(self):
        self.assertEqual(NICHES_DOC["schema_version"], 1)
        self.assertTrue(iso(NICHES_DOC["checked_on"]))
        self.assertGreaterEqual(len(NICHES_DOC["niches"]), 8)
        self.assertLessEqual(len(NICHES_DOC["niches"]), 10)

    def test_required_categories(self):
        for c in ("civil", "tax", "accounting", "company", "data", "consumer", "e-commerce", "digital-content",
                  "advertising", "employment", "ip", "education", "it-park", "health-safety", "food-safety"):
            self.assertIn(c, self.CATS)

    def test_labels(self):
        items = list(self.CATS.items()) + list(NICHES_DOC["niches"].items())
        for key, item in items:
            with self.subTest(key=key):
                self.assertEqual(set(item["label"]), LANGS)
                self.assertTrue(all(v.strip() for v in item["label"].values()))

    def test_category_acts_exist_and_unique(self):
        for c, cat in self.CATS.items():
            with self.subTest(category=c):
                self.assertTrue(cat["acts"])
                self.assertEqual(len(cat["acts"]), len(set(cat["acts"])))
                self.assertEqual([i for i in cat["acts"] if i not in ACTS], [])

    def test_every_act_used(self):
        used = {i for cat in self.CATS.values() for i in cat["acts"]}
        self.assertEqual(sorted(set(ACTS) - used), [])

    def test_general_b2c_and_niche_categories_exist(self):
        refs = NICHES_DOC["general"] + NICHES_DOC["b2c"]
        for n in NICHES_DOC["niches"].values():
            self.assertTrue(n["categories"])
            refs += n["categories"]
        self.assertEqual([c for c in refs if c not in self.CATS], [])
        self.assertEqual(NICHES_DOC["general"], ["civil", "tax", "accounting", "company", "data"])
        self.assertEqual(NICHES_DOC["b2c"], ["consumer"])

    def test_every_category_reachable(self):
        reachable = set(NICHES_DOC["general"]) | set(NICHES_DOC["b2c"])
        for n in NICHES_DOC["niches"].values():
            reachable |= set(n["categories"])
        self.assertEqual(sorted(set(self.CATS) - reachable), [])

    def test_general_categories_cover_every_jurisdiction(self):
        # why: the wizard filters by the user's countries; a general category empty for a country is a gap
        for c in ("civil", "tax", "accounting", "company", "data"):
            jur = {ACTS[i]["jurisdiction"] for i in self.CATS[c]["acts"]}
            self.assertTrue({"MD", "RO"} <= jur, c)


class LawMaps(unittest.TestCase):
    def test_every_cited_act_is_in_the_catalog(self):
        maps = sorted(SKILLS.glob("legal-*/references/law-map.md"))
        self.assertTrue(maps, "no law maps found")
        missing = []
        for path in maps:
            for cited in CITED.findall(path.read_text(encoding="utf-8")):
                if cited not in ACTS and cited not in NOT_ACTS:
                    missing.append(f"{path.parent.parent.name}: {cited}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
