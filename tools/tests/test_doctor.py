"""Tests of tools/doctor.py helpers (no real install is touched)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import doctor  # noqa: E402


class ProfileDir(unittest.TestCase):
    def test_no_config_means_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, source = doctor.profile_dir(Path(tmp) / "none.json")
            self.assertEqual(path, doctor.DEFAULT_PROFILE)
            self.assertIn("default", source)

    def test_config_path_is_expanded(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "c.json"
            cfg.write_text(json.dumps({"profile_dir": "~/firma-legal"}), encoding="utf-8")
            path, _ = doctor.profile_dir(cfg)
            self.assertEqual(path, Path.home() / "firma-legal")

    def test_broken_config_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "c.json"
            for text in ("{not json", json.dumps({"profile_dir": ""}), json.dumps({})):
                cfg.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(SystemExit):
                    doctor.profile_dir(cfg)


class EngineSkills(unittest.TestCase):
    def test_lists_only_folders_with_skill_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills/a").mkdir(parents=True)
            (root / "skills/a/SKILL.md").write_text("x", encoding="utf-8")
            (root / "skills/b").mkdir()
            self.assertEqual(doctor.engine_skills(root), ["a"])
            self.assertEqual(doctor.engine_skills(root / "none"), [])

    def test_missing_venv_is_not_ready(self):
        self.assertFalse(doctor.venv_ready(Path("/nonexistent/python")))

    def test_browser_needs_package_and_chromium(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            (cache / "chromium-1").mkdir(parents=True)
            # a Chromium in the shared cache is not enough without the package in .venv
            self.assertFalse(doctor.playwright_ready(Path("/nonexistent/python"), (cache,)))
            # python3 here has no playwright package
            self.assertFalse(doctor.playwright_ready(Path(sys.executable), (cache,)))
            self.assertFalse(doctor.playwright_ready(Path(sys.executable), (Path(tmp) / "none",)))


class Vendor(unittest.TestCase):
    """VENDOR.json says which release is installed and which hosts the scripts read: it must stay true."""

    ROOT = Path(__file__).resolve().parents[2]

    def setUp(self):
        self.v = json.loads((self.ROOT / "VENDOR.json").read_text(encoding="utf-8"))

    def test_skills_and_modules_match(self):
        self.assertEqual(sorted(self.v["skills"]), doctor.engine_skills(self.ROOT))
        mods = json.loads((self.ROOT / "skills/legal-workflow/assets/modules.json").read_text(encoding="utf-8"))
        for m in mods["modules"].values():
            role = "core module" if m["core"] else "optional module"
            self.assertTrue(self.v["skills"][m["skill"]].startswith(role), m["skill"])

    def test_version_is_the_latest_release_in_the_changelog(self):
        import re
        text = (self.ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        m = re.search(r"^## \[?(\d+\.\d+\.\d+)\]? — (\d{4}-\d{2}-\d{2})", text, re.M)
        self.assertIsNotNone(m, "CHANGELOG has no released version heading '## X.Y.Z — YYYY-MM-DD'")
        self.assertEqual((m.group(1), m.group(2)), (self.v["version"], self.v["released"]))
        self.assertIn(self.v["version"], doctor.engine_version(self.ROOT))

    def test_every_host_the_watch_scripts_read_is_declared(self):
        import re
        hosts = set()
        for py in (self.ROOT / "skills/legal-watch/scripts").rglob("*.py"):
            hosts |= set(re.findall(r"https?://([a-z0-9-]+(?:\.[a-z0-9-]+)+)", py.read_text(encoding="utf-8")))
        hosts -= {"schemas.openxmlformats.org"}   # an XML namespace, not a request
        self.assertLessEqual(hosts, set(self.v["network"]["hosts"]))


if __name__ == "__main__":
    unittest.main()
