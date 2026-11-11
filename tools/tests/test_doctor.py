"""Tests of tools/doctor.py helpers (no real install is touched)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import doctor  # noqa: E402


def _can_symlink() -> bool:
    """why: ordinary Windows (no admin, no Developer Mode) refuses symlinks; those tests are skipped there."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.symlink(tmp, os.path.join(tmp, "probe"), target_is_directory=True)
        except (OSError, NotImplementedError):
            return False
    return True


CAN_SYMLINK = _can_symlink()


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


class SkillSource(unittest.TestCase):
    """A skill counts as installed through a symlink (install.sh), a junction (install.ps1) or a hand copy."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.src, self.skills = base / "engine" / "skills" / "legal-x", base / "skills"
        self.src.mkdir(parents=True)
        self.skills.mkdir()
        (self.src / "SKILL.md").write_text("---\nname: legal-x\n---\n", encoding="utf-8")

    @unittest.skipUnless(CAN_SYMLINK, "symlinks need admin rights or Developer Mode on Windows")
    def test_link_to_this_engine(self):
        dst = self.skills / "legal-x"
        dst.symlink_to(self.src, target_is_directory=True)
        self.assertEqual(doctor.skill_source(dst, self.src), "this repo")

    @unittest.skipUnless(os.name == "nt", "junctions exist only on Windows")
    def test_real_junction_on_windows(self):
        import _winapi  # CPython's own junction call: what install.ps1 makes, no admin rights needed
        dst = self.skills / "legal-x"
        _winapi.CreateJunction(str(self.src), str(dst))
        self.assertEqual(doctor.skill_source(dst, self.src), "this repo")

    @unittest.skipUnless(CAN_SYMLINK, "simulated with a symlink")
    def test_link_that_is_not_a_symlink_counts(self):
        # why: a junction is not `is_symlink()`, but `resolve()` follows it; acceptance must not depend on the
        # link kind, so the answer stays the same when the link does not look like a symlink.
        dst = self.skills / "legal-x"
        dst.symlink_to(self.src, target_is_directory=True)
        with mock.patch.object(Path, "is_symlink", return_value=False):
            self.assertEqual(doctor.skill_source(dst, self.src), "this repo")

    def test_copy_of_this_engine_and_another_copy(self):
        dst = self.skills / "legal-x"
        dst.mkdir()
        (dst / "SKILL.md").write_bytes((self.src / "SKILL.md").read_bytes())
        self.assertTrue(doctor.skill_source(dst, self.src).startswith("a copy of this repo"))
        (dst / "SKILL.md").write_text("---\nname: legal-x\n---\nolder\n", encoding="utf-8")
        self.assertEqual(doctor.skill_source(dst, self.src), "another copy")

    def test_missing(self):
        self.assertEqual(doctor.skill_source(self.skills / "legal-x", self.src), "missing")
        (self.skills / "legal-x").mkdir()   # an empty folder is not an installed skill
        self.assertEqual(doctor.skill_source(self.skills / "legal-x", self.src), "missing")


class PlatformHints(unittest.TestCase):
    def test_engine_python_and_install_hints(self):
        self.assertEqual(doctor.VENV_PY, doctor._engine_env.venv_python(doctor.ROOT))
        self.assertIn(doctor.INSTALL, ("./install.sh", doctor._engine_env.install_hint(windows=True)))
        self.assertTrue(doctor.playwright_hint(windows=True).startswith("$env:WITH_PLAYWRIGHT=1; "))
        self.assertTrue(doctor.playwright_hint(windows=False).startswith("WITH_PLAYWRIGHT=1 "))

    def test_playwright_caches_cover_three_systems(self):
        self.assertEqual(len(doctor.PLAYWRIGHT_CACHES), 3)   # macOS, Linux, Windows %LOCALAPPDATA%
        self.assertTrue(all(c.name == "ms-playwright" for c in doctor.PLAYWRIGHT_CACHES))


class WatchIssues(unittest.TestCase):
    def test_counts_open_problems_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            prof = Path(tmp)
            self.assertEqual(doctor.open_watch_issues(prof), 0)
            (prof / "laws").mkdir()
            (prof / "laws" / "issues.json").write_text("not json", encoding="utf-8")
            self.assertEqual(doctor.open_watch_issues(prof), 0)
            (prof / "laws" / "issues.json").write_text(json.dumps(
                {"acts": {"a": {"state": "open"}, "b": {"state": "resolved"}, "c": {"state": "open"}}}), encoding="utf-8")
            self.assertEqual(doctor.open_watch_issues(prof), 2)


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
