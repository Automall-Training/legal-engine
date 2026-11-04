"""Consistency of every engine skill: frontmatter, relative links, JSON files, module templates.

Skills are mostly instructions; these checks catch the drift that breaks them silently: a renamed reference, a link
to a file that moved, a template the profile script would refuse.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS = ROOT / "skills"
sys.path.insert(0, str(SKILLS / "legal-workflow" / "scripts"))
import legal_profile as lp  # noqa: E402

CATALOG = json.loads((SKILLS / "legal-workflow" / "assets" / "modules.json").read_text(encoding="utf-8"))
LINK = re.compile(r"\]\(([^)\s]+)\)")


def skill_dirs() -> list[Path]:
    return sorted(p.parent for p in SKILLS.glob("*/SKILL.md"))


def frontmatter(path: Path) -> dict[str, str]:
    """Flat `key: value` lines only; a multi-line YAML value fails with the file named."""
    block = path.read_text(encoding="utf-8").split("---")[1]
    lines = block.strip().splitlines()
    bad = [line for line in lines if ": " not in line]
    if bad:
        raise AssertionError(f"{path}: frontmatter lines must be 'key: value', got {bad[0]!r}")
    return dict(line.split(": ", 1) for line in lines)


class Frontmatter(unittest.TestCase):
    def test_name_matches_folder_and_description_present(self):
        for skill in skill_dirs():
            with self.subTest(skill=skill.name):
                meta = frontmatter(skill / "SKILL.md")
                self.assertEqual(meta["name"], skill.name)
                self.assertGreater(len(meta.get("description", "")), 80)

    def test_every_installed_module_is_in_the_catalog(self):
        skills = {m["skill"] for m in CATALOG["modules"].values()}
        helpers = {"legal-workflow", "legal-workflow-setup", "legal-workflow-update"}
        for skill in skill_dirs():
            with self.subTest(skill=skill.name):
                self.assertIn(skill.name, skills | helpers)


class Links(unittest.TestCase):
    def test_relative_links_resolve(self):
        for md in SKILLS.rglob("*.md"):
            for target in LINK.findall(md.read_text(encoding="utf-8")):
                if re.match(r"[a-z]+:", target) or target.startswith("#"):
                    continue  # why: web links are checked live in a matter, anchors are not files
                with self.subTest(file=str(md.relative_to(ROOT)), link=target):
                    self.assertTrue((md.parent / target.split("#")[0]).exists())


class JsonFiles(unittest.TestCase):
    def test_every_json_parses(self):
        for path in SKILLS.rglob("*.json"):
            with self.subTest(file=str(path.relative_to(ROOT))):
                json.loads(path.read_text(encoding="utf-8"))

    def test_module_templates_are_accepted_by_matter_update(self):
        """A template with module_data is the exact payload of `matter update`; the script must take it."""
        templates = [p for p in SKILLS.glob("*/templates/module-data.json")
                     if "module_data" in json.loads(p.read_text(encoding="utf-8"))]
        self.assertTrue(templates)
        with tempfile.TemporaryDirectory() as tmp:
            prof = Path(tmp) / "profile"
            (prof / "matters").mkdir(parents=True)
            for path in templates:
                with self.subTest(template=str(path.relative_to(ROOT))):
                    module = next(mid for mid, m in CATALOG["modules"].items() if m["skill"] == path.parent.parent.name)
                    mid = lp.matter_new(prof, module, "Template check", module, CATALOG, "2026-11-04")["id"]
                    data = json.loads(path.read_text(encoding="utf-8"))
                    lp.matter_update(prof, mid, data)
                    intake = json.loads((prof / "matters" / mid / "intake.json").read_text(encoding="utf-8"))
                    self.assertEqual(intake["module_data"], data["module_data"])


class OptionalModules(unittest.TestCase):
    def test_optional_module_checks_its_switch_first(self):
        """An optional module must stop when the user turned it off (profile.md, module states)."""
        for mid, mod in CATALOG["modules"].items():
            skill = SKILLS / mod["skill"]
            if mod["core"] or not skill.is_dir():
                continue
            with self.subTest(module=mid):
                text = (skill / "SKILL.md").read_text(encoding="utf-8")
                before = text.split("## Route")[0]
                self.assertIn(f"legal_profile.py module {mid}`", before)
                for state in ("`off`", "`unset`", "`on`"):
                    self.assertIn(state, before)

    def test_modules_hand_documents_to_the_contract_tools_by_path(self):
        for mid, mod in CATALOG["modules"].items():
            skill = SKILLS / mod["skill"]
            if mod["core"] or not skill.is_dir():
                continue
            with self.subTest(module=mid):
                self.assertIn("<skill-dir>/../legal-contracts/", (skill / "SKILL.md").read_text(encoding="utf-8"))
                for md in [skill / "SKILL.md", *skill.glob("references/*.md")]:
                    for card in re.findall(r"(\d\d-[a-z-]+\.ro\.md)", md.read_text(encoding="utf-8")):
                        models = SKILLS / "legal-contracts" / "references" / "models"
                        self.assertTrue((models / card).is_file(), f"{md.name}: {card}")


if __name__ == "__main__":
    unittest.main()
