"""Tests of scripts/legal_profile.py on throw-away profiles (the real profile is never touched)."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import legal_profile as lp  # noqa: E402

CATALOG = lp.load_catalog()
STATUS_TABLE = """# Integration status

| Step | Status | Updated | Note |
|---|---|---|---|
| firms | done | 2026-11-04 | |
| audience | skipped | 2026-11-04 | |
| modules | done | 2026-11-04 | |
| language | done | 2026-11-04 | |
| side-risk | done | 2026-11-04 | default norms |
"""


def make_profile(root: Path, *, status: str = STATUS_TABLE, modules: dict | None = None) -> Path:
    prof = root / "legal-profile"
    (prof / "context").mkdir(parents=True)
    for name in ("company.md", "language.md", "side-and-risk.md"):
        (prof / "context" / name).write_text("x\n", encoding="utf-8")
    (prof / "context" / "integration-status.md").write_text(status, encoding="utf-8")
    mods = {"schema_version": 1, "privacy": True, "consumer": False} if modules is None else modules
    (prof / "modules.json").write_text(json.dumps(mods), encoding="utf-8")
    return prof


def make_siblings(root: Path, *skills: str) -> Path:
    sib = root / "skills"
    for name in skills:
        (sib / name).mkdir(parents=True)
        (sib / name / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    sib.mkdir(exist_ok=True)
    return sib


class TmpCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class ResolveProfile(TmpCase):
    def test_no_config_means_default(self):
        path, source = lp.resolve_profile(self.root / "none.json")
        self.assertEqual(path, lp.DEFAULT_PROFILE)
        self.assertIn("default", source)

    def test_config_path_is_expanded(self):
        cfg = self.root / "c.json"
        cfg.write_text(json.dumps({"profile_dir": "~/firma-legal"}), encoding="utf-8")
        path, source = lp.resolve_profile(cfg)
        self.assertEqual(path, Path.home() / "firma-legal")
        self.assertIn("config", source)

    def test_broken_config_fails_loudly(self):
        cfg = self.root / "c.json"
        for text in ("{not json", json.dumps({"profile_dir": ""}), json.dumps({}), json.dumps([1]),
                     json.dumps({"profile_dir": "relative/path"})):
            cfg.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(lp.ConfigError):
                lp.resolve_profile(cfg)

    def test_profile_inside_engine_is_refused(self):
        cfg = self.root / "c.json"
        for inside in (lp.ENGINE_ROOT, lp.ENGINE_ROOT / "legal-profile"):
            cfg.write_text(json.dumps({"profile_dir": str(inside)}), encoding="utf-8")
            with self.subTest(inside=inside), self.assertRaises(lp.ProfileLocationError):
                lp.resolve_profile(cfg)


class Catalog(TmpCase):
    def test_shipped_catalog_is_valid(self):
        self.assertEqual(set(lp.optional_ids(CATALOG)), {"privacy", "consumer", "trademark", "employment"})
        self.assertTrue(set(lp.STEP_FILES) <= set(CATALOG["steps"]))

    def test_broken_catalogs(self):
        bad = [
            "{",
            json.dumps({"steps": [], "modules": {}}),
            json.dumps({"steps": ["a"], "base_needs": ["b"], "modules": {"m": {"skill": "s", "core": True}}}),
            json.dumps({"steps": ["a"], "modules": {"m": {"skill": "s"}}}),
            json.dumps({"steps": ["a"], "modules": {"m": {"skill": "s", "core": True, "needs": ["z"]}}}),
        ]
        path = self.root / "cat.json"
        for text in bad:
            path.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(lp.CatalogError):
                lp.load_catalog(path)

    def test_missing_catalog(self):
        with self.assertRaises(lp.CatalogError):
            lp.load_catalog(self.root / "none.json")


class Modules(TmpCase):
    def test_missing_file_is_none(self):
        self.assertIsNone(lp.read_modules(self.root, CATALOG))

    def test_unset_optional_modules_are_off(self):
        prof = make_profile(self.root)
        self.assertEqual(lp.read_modules(prof, CATALOG),
                         {"privacy": True, "consumer": False, "trademark": False, "employment": False})

    def test_bad_modules_files(self):
        for content in ("{", json.dumps({"privacy": True}), json.dumps({"schema_version": 2}),
                        json.dumps({"schema_version": 1, "contracts": True}),
                        json.dumps({"schema_version": 1, "privacy": "yes"}), json.dumps([1])):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / "modules.json").write_text(content, encoding="utf-8")
                with self.assertRaises(lp.ModulesFileError):
                    lp.read_modules(Path(tmp), CATALOG)


class Steps(TmpCase):
    def test_table_is_read_and_missing_rows_are_pending(self):
        steps = lp.read_steps(make_profile(self.root), CATALOG)
        self.assertEqual(steps["firms"], "done")
        self.assertEqual(steps["audience"], "skipped")
        self.assertEqual(steps["niches"], "pending")

    def test_done_without_file_is_pending(self):
        prof = make_profile(self.root)
        (prof / "context" / "language.md").unlink()
        self.assertEqual(lp.read_steps(prof, CATALOG)["language"], "pending")

    def test_unknown_state_fails(self):
        prof = make_profile(self.root, status="| firms | maybe | | |\n")
        with self.assertRaises(lp.StatusFileError):
            lp.read_steps(prof, CATALOG)

    def test_no_status_file_all_pending(self):
        self.assertEqual(set(lp.read_steps(self.root, CATALOG).values()), {"pending"})


class Status(TmpCase):
    def test_ready_profile(self):
        prof = make_profile(self.root)
        sib = make_siblings(self.root, "legal-contracts", "legal-privacy", "legal-consumer")
        out = lp.status(prof, "test", CATALOG, siblings=sib)
        self.assertTrue(out["ready"])
        self.assertEqual(out["missing_steps"], [])
        self.assertEqual(out["modules"]["contracts"], "core")
        self.assertEqual(out["modules"]["privacy"], "on")
        self.assertEqual(out["modules"]["consumer"], "off")
        self.assertEqual(out["modules"]["employment"], "not-installed")

    def test_module_with_extra_needs(self):
        prof = make_profile(self.root)
        sib = make_siblings(self.root, "legal-watch")
        out = lp.status(prof, "test", CATALOG, module="watch", siblings=sib)
        self.assertFalse(out["ready"])
        self.assertEqual(out["missing_steps"], ["niches", "laws"])
        self.assertEqual(out["module_state"], "core")

    def test_missing_profile(self):
        out = lp.status(self.root / "nope", "test", CATALOG, siblings=make_siblings(self.root))
        self.assertFalse(out["exists"])
        self.assertFalse(out["ready"])
        self.assertEqual(out["missing_steps"], CATALOG["base_needs"])

    def test_unknown_module(self):
        with self.assertRaises(lp.LegalProfileError):
            lp.status(make_profile(self.root), "test", CATALOG, module="tax")

    def test_switches_none_means_off(self):
        sib = make_siblings(self.root, "legal-privacy")
        self.assertEqual(lp.module_state("privacy", CATALOG, None, sib), "off")


class Matters(TmpCase):
    def setUp(self):
        super().setUp()
        self.prof = make_profile(self.root)

    def test_new_creates_folder_intake_and_log(self):
        out = lp.matter_new(self.prof, "nda-acme", "NDA | with Acme\nSRL", "contracts", CATALOG, "2026-11-04")
        self.assertEqual(out["id"], "2026-11-04-nda-acme")
        intake = json.loads((self.prof / "matters" / out["id"] / "intake.json").read_text(encoding="utf-8"))
        self.assertEqual(intake["task_id"], out["id"])
        self.assertEqual(intake["module"], "contracts")
        self.assertEqual(intake["title"], "NDA | with Acme SRL")
        self.assertTrue((self.prof / "matters" / out["id"] / "input").is_dir())
        self.assertTrue((self.prof / "matters" / out["id"] / "output").is_dir())
        self.assertEqual(lp.matter_list(self.prof)[0]["title"], "NDA | with Acme SRL")
        log = (self.prof / "matters" / "log.md").read_text(encoding="utf-8")
        self.assertTrue(log.startswith("# Matters log"))
        self.assertIn("| 2026-11-04 | 2026-11-04-nda-acme | contracts | opened | NDA \\| with Acme SRL |", log)

    def test_same_name_gets_suffix(self):
        ids = [lp.matter_new(self.prof, "nda", "t", "contracts", CATALOG, "2026-11-04")["id"] for _ in range(3)]
        self.assertEqual(ids, ["2026-11-04-nda", "2026-11-04-nda-02", "2026-11-04-nda-03"])

    def test_bad_inputs(self):
        cases = [("NDA", "t", "contracts", None), ("a" * 61, "t", "contracts", None),
                 ("nda", "t", "tax", None), ("nda", "  ", "contracts", None),
                 ("nda", "t", "contracts", "04.11.2026")]
        for slug, title, module, date in cases:
            with self.subTest(slug=slug, module=module, date=date), self.assertRaises(lp.MatterError):
                lp.matter_new(self.prof, slug, title, module, CATALOG, date)

    def test_no_profile(self):
        with self.assertRaises(lp.MatterError):
            lp.matter_new(self.root / "nope", "nda", "t", "contracts", CATALOG)

    def test_log_and_list(self):
        a = lp.matter_new(self.prof, "nda", "NDA", "contracts", CATALOG, "2026-11-01")["id"]
        b = lp.matter_new(self.prof, "policy", "Privacy policy", "privacy", CATALOG, "2026-11-02")["id"]
        lp.matter_log(self.prof, a, "waiting", "asked for the counterparty name", "2026-11-03")
        lp.matter_log(self.prof, a, "note", "draft v1 ready", "2026-11-04")
        lp.matter_log(self.prof, b, "done", "", "2026-11-04")
        items = {i["id"]: i for i in lp.matter_list(self.prof)}
        self.assertEqual(items[a]["status"], "waiting")
        self.assertEqual(items[a]["updated"], "2026-11-04")
        self.assertEqual(items[a]["title"], "NDA")
        self.assertEqual(items[b]["status"], "done")
        self.assertEqual([i["id"] for i in lp.matter_list(self.prof, only_open=True)], [a])

    def test_log_errors(self):
        a = lp.matter_new(self.prof, "nda", "NDA", "contracts", CATALOG)["id"]
        with self.assertRaises(lp.MatterError):
            lp.matter_log(self.prof, a, "signed")
        with self.assertRaises(lp.MatterError):
            lp.matter_log(self.prof, "../etc", "note")
        with self.assertRaises(lp.MatterError):
            lp.matter_log(self.prof, "2026-01-01-none", "note")
        (self.prof / "matters" / a / "intake.json").write_text("{", encoding="utf-8")
        with self.assertRaises(lp.MatterError):
            lp.matter_log(self.prof, a, "note")

    def test_list_without_log(self):
        self.assertEqual(lp.matter_list(self.prof), [])


class Cli(TmpCase):
    def run_cli(self, *args: str, config: dict | None = None, siblings: Path | None = None) -> tuple[int, str, str]:
        cfg = self.root / "config.json"
        if config is not None:
            cfg.write_text(json.dumps(config), encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(lp, "CONFIG", cfg), mock.patch.object(lp, "SIBLINGS", siblings or self.root / "none"), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = lp.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_where_status_module_and_matters(self):
        prof = make_profile(self.root)
        cfg = {"profile_dir": str(prof)}
        sib = make_siblings(self.root, "legal-contracts")
        code, out, _ = self.run_cli("where", config=cfg)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["profile"], str(prof))
        code, out, _ = self.run_cli("status", "--module", "contracts", config=cfg, siblings=sib)
        self.assertTrue(json.loads(out)["ready"])
        code, out, _ = self.run_cli("module", "privacy", config=cfg, siblings=sib)
        self.assertEqual(json.loads(out)["state"], "not-installed")
        code, out, _ = self.run_cli("matter", "new", "--slug", "nda", "--title", "NDA", "--module", "contracts",
                                    "--date", "2026-11-04", config=cfg)
        self.assertEqual(json.loads(out)["id"], "2026-11-04-nda")
        code, out, _ = self.run_cli("matter", "log", "2026-11-04-nda", "--event", "done", config=cfg)
        self.assertEqual(code, 0)
        code, out, _ = self.run_cli("matter", "list", "--open", config=cfg)
        self.assertEqual(json.loads(out), [])

    def test_errors_exit_2_with_message(self):
        code, out, err = self.run_cli("where", config={"profile_dir": ""})
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("ConfigError", err)
        code, _, err = self.run_cli("module", "tax", config={"profile_dir": str(self.root / "p")})
        self.assertEqual(code, 2)
        self.assertIn("unknown module", err)


if __name__ == "__main__":
    unittest.main()
