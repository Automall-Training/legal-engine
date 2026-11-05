"""Command lines, the engine-folder guard, the environment re-run and the shipped redline example."""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R, B, S, T, ENV = (module(n) for n in ("docx_redline", "build_docx", "check_structure", "check_ro_style",
                                       "_engine_env"))


def run(main, *argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue() + err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)


class EngineGuardTests(Base):
    def test_inside_engine_refused(self):
        with self.assertRaisesRegex(ValueError, "engine folder"):
            ENV.refuse_inside_engine(ENV.ENGINE_ROOT / "skills" / "x.docx")
        with self.assertRaises(R.RedlineError):
            ENV.refuse_inside_engine(ENV.ENGINE_ROOT, R.RedlineError)

    def test_case_changed_path_refused(self):
        # why: on a case-insensitive disk another spelling reaches the same folder.
        other = Path(str(ENV.ENGINE_ROOT).swapcase())
        if not other.exists():
            self.skipTest("case-sensitive file system")
        with self.assertRaisesRegex(ValueError, "engine folder"):
            ENV.refuse_inside_engine(other / "new" / "out.docx")

    def test_outside_engine_allowed(self):
        self.assertEqual(ENV.refuse_inside_engine(self.dir / "out.docx"), (self.dir / "out.docx").resolve())

    def test_builder_refuses_engine_folder(self):
        spec = self.dir / "spec.json"
        spec.write_text(json.dumps({"title": "T", "blocks": []}), encoding="utf-8")
        code, out = run(B.main, str(spec), str(ENV.ENGINE_ROOT / "never.docx"))
        self.assertEqual(code, 2)
        self.assertIn("engine folder", out)
        self.assertFalse((ENV.ENGINE_ROOT / "never.docx").exists())


class ReexecTests(Base):
    def test_missing_environment_is_a_clear_stop(self):
        with mock.patch.dict(os.environ, {}, clear=False), self.assertRaises(SystemExit) as stop, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            os.environ.pop(ENV.GUARD, None)
            ENV.reexec(__file__, "lxml", venv=self.dir / "no-python")
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("./install.sh", out.getvalue())

    def test_guard_prevents_a_loop(self):
        fake = self.dir / "python"
        fake.write_text("", encoding="utf-8")
        with mock.patch.dict(os.environ, {ENV.GUARD: "1"}), mock.patch.object(ENV.os, "execv") as execv, \
                self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
            ENV.reexec(__file__, "lxml", venv=fake)
        execv.assert_not_called()

    def test_reruns_with_engine_python(self):
        fake = self.dir / "python"
        fake.write_text("", encoding="utf-8")
        with mock.patch.dict(os.environ, {}, clear=False), mock.patch.object(ENV.os, "execv") as execv, \
                mock.patch.object(ENV.sys, "argv", ["x.py", "inspect", "a.docx"]), \
                contextlib.redirect_stdout(io.StringIO()):
            os.environ.pop(ENV.GUARD, None)
            with self.assertRaises(SystemExit):  # why: the real execv never returns; the mock does
                ENV.reexec(__file__, "lxml", venv=fake)
            self.assertEqual(os.environ[ENV.GUARD], "1")
        execv.assert_called_once_with(str(fake), [str(fake), str(Path(__file__).resolve()), "inspect", "a.docx"])


class BuildCliTests(Base):
    def test_create_then_refuse_overwrite(self):
        spec = self.dir / "spec.json"
        shutil.copy(ROOT / "templates" / "document.json", spec)
        target = self.dir / "draft.docx"
        code, out = run(B.main, str(spec), str(target))
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["status"], "created")
        code, out = run(B.main, str(spec), str(target))
        self.assertEqual(code, 2)
        self.assertIn("no overwrite", out)

    def test_bad_specs(self):
        bad = self.dir / "bad.json"
        bad.write_text("[]", encoding="utf-8")
        self.assertEqual(run(B.main, str(bad), str(self.dir / "c.docx"))[0], 2)
        bad.write_text("{", encoding="utf-8")
        self.assertEqual(run(B.main, str(bad), str(self.dir / "a.docx"))[0], 2)
        for blocks in ([{"type": "image"}], [{"type": "table", "rows": [["a", "b"], ["c"]]}]):
            bad.write_text(json.dumps({"title": "T", "blocks": blocks}), encoding="utf-8")
            self.assertEqual(run(B.main, str(bad), str(self.dir / "b.docx"))[0], 2)

    def test_heading_block(self):
        spec = self.dir / "s.json"
        spec.write_text(json.dumps({"title": "T", "blocks": [{"type": "heading", "text": "Obiectul", "level": 2}]}),
                        encoding="utf-8")
        self.assertEqual(run(B.main, str(spec), str(self.dir / "h.docx"))[0], 0)


class RedlineCliTests(Base):
    """Scenario D1: the shipped synthetic original + agreed changes → real revisions, clean = accepted."""

    def test_shipped_example_end_to_end(self):
        original = self.dir / "original.docx"
        shutil.copy(ROOT / "assets" / "original.docx", original)
        code, out = run(R.main, "inspect", str(original))
        self.assertEqual(code, 0)
        paragraphs = json.loads(out)["paragraphs"]
        self.assertEqual(paragraphs[2]["text"], "1. Plata se efectuează în 10 zile de la primirea facturii.")
        code, out = run(R.main, "apply", str(original), str(ROOT / "assets" / "changes.json"), str(self.dir / "out"))
        self.assertEqual(code, 0, out)
        result = json.loads(out)
        self.assertTrue(result["accept_equals_clean"] and result["reject_equals_original"])
        self.assertEqual(result["revisions"], 3)
        code, out = run(R.main, "verify", str(original), str(self.dir / "out/tracked.docx"),
                        str(self.dir / "out/clean.docx"))
        self.assertEqual(code, 0, out)

    def test_shipped_redline_example_still_verifies(self):
        ex = ROOT / "assets" / "redline-example"
        code, out = run(R.main, "verify", str(ROOT / "assets" / "original.docx"), str(ex / "tracked.docx"),
                        str(ex / "clean.docx"))
        self.assertEqual(code, 0, out)

    def test_malformed_plans_exit_2(self):
        plan = self.dir / "plan.json"
        for bad in ([], {"changes": ["a"]}, {"author": "x", "changes": [{"paragraph": True, "old": "a", "new": "b",
                                                                          "expected_paragraph": "a"}]},
                    {"author": "x", "changes": [{"paragraph": 2, "old": 1, "new": "b", "expected_paragraph": "a"}]},
                    {"author": 5, "changes": []}, {"changes": [{"paragraph": 0, "part": 3}]}):
            plan.write_text(json.dumps(bad), encoding="utf-8")
            with self.subTest(plan=bad):
                code, out = run(R.main, "apply", str(ROOT / "assets" / "original.docx"), str(plan), str(self.dir / "o"))
                self.assertEqual(code, 2, out)
                self.assertFalse((self.dir / "o").exists())

    def test_failed_verification_leaves_no_output(self):
        with mock.patch.object(R, "verify", side_effect=R.RedlineError("boom")):
            with self.assertRaises(R.RedlineError):
                R.apply(ROOT / "assets" / "original.docx", json.loads((ROOT / "assets" / "changes.json").read_text(
                    encoding="utf-8")), self.dir / "out")
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_text_box_paragraph_is_not_a_target(self):
        from lxml import etree
        xml = (f'<w:p xmlns:w="{R.W}"><w:r><w:pict><w:txbxContent><w:p><w:r><w:t>x</w:t></w:r></w:p>'
               '</w:txbxContent></w:pict></w:r></w:p>')
        inner = etree.fromstring(xml).find(f".//{{{R.W}}}txbxContent/{{{R.W}}}p")
        self.assertFalse(R.simple(inner))

    def test_errors_exit_2(self):
        missing = self.dir / "missing.docx"
        self.assertEqual(run(R.main, "inspect", str(missing))[0], 2)
        code, out = run(R.main, "apply", str(ROOT / "assets" / "original.docx"), str(ROOT / "assets" / "changes.json"),
                        str(ENV.ENGINE_ROOT / "never-out"))
        self.assertEqual(code, 2)
        self.assertIn("engine folder", out)
        self.assertFalse((ENV.ENGINE_ROOT / "never-out").exists())


class StructureCliTests(Base):
    def test_codes(self):
        self.assertEqual(run(S.main)[0], 2)
        ok = self.dir / "ok.md"
        ok.write_text("## 1 Obiect\n1.1 Text.\n1.2 Text.\n", encoding="utf-8")
        self.assertEqual(run(S.main, str(ok))[0], 0)
        dup = self.dir / "dup.md"
        dup.write_text("## 1 Obiect\n1.1 Text.\n1.1 Alt.\n", encoding="utf-8")
        report = self.dir / "report.json"
        self.assertEqual(run(S.main, str(dup), "--report", str(report))[0], 1)
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"], "needs_review")

    def test_manifest_and_engine_guard(self):
        manifest = self.dir / "m.json"
        manifest.write_text(json.dumps({"total": "100", "installments": ["50", "40"]}), encoding="utf-8")
        code, out = run(S.main, "--commercial", str(manifest))
        self.assertEqual(code, 1)
        self.assertIn("installments", out)
        manifest.write_text(json.dumps({"total": 100}), encoding="utf-8")
        self.assertEqual(run(S.main, "--commercial", str(manifest))[0], 2)
        ok = self.dir / "ok.md"
        ok.write_text("Text.\n", encoding="utf-8")
        code, out = run(S.main, str(ok), "--report", str(ENV.ENGINE_ROOT / "never.json"))
        self.assertEqual(code, 2)
        self.assertFalse((ENV.ENGINE_ROOT / "never.json").exists())

    def test_report_never_overwrites_an_input(self):
        """Codex review: `--report contract.md` (or a link to it) replaced the contract with JSON."""
        doc = self.dir / "contract.md"
        doc.write_text("## 1 Obiect\n1.1 Text.\n", encoding="utf-8")
        link = self.dir / "link.md"
        link.symlink_to(doc)
        for target in (doc, link):
            with self.subTest(target=target.name):
                self.assertEqual(run(S.main, str(doc), "--report", str(target))[0], 2)
                self.assertEqual(doc.read_text(encoding="utf-8"), "## 1 Obiect\n1.1 Text.\n")
        voice = self.dir / "b.ro.md"
        voice.write_text("Restituim prețul.\n", encoding="utf-8")
        self.assertEqual(run(T.main, str(voice), "--report", str(voice))[0], 2)
        self.assertEqual(voice.read_text(encoding="utf-8"), "Restituim prețul.\n")


class StyleCliTests(Base):
    def test_codes(self):
        clean = self.dir / "a.ro.md"
        clean.write_text("Furnizorul prestează serviciul.\n", encoding="utf-8")
        self.assertEqual(run(T.main, str(clean))[0], 0)
        voice = self.dir / "b.ro.md"
        voice.write_text("Restituim prețul.\n", encoding="utf-8")
        report = self.dir / "r.json"
        self.assertEqual(run(T.main, str(voice), "--root", str(self.dir), "--report", str(report))[0], 1)
        found = json.loads(report.read_text(encoding="utf-8"))["candidates"][0]
        decisions = self.dir / "d.json"
        decisions.write_text(json.dumps({"exceptions": [{"id": found["id"], "text_sha256": found["text_sha256"],
                                                         "role": "false_positive", "reason": "test"}]}),
                             encoding="utf-8")
        self.assertEqual(run(T.main, str(voice), "--root", str(self.dir), "--review", str(decisions))[0], 0)
        decisions.write_text(json.dumps({"exceptions": [{"id": "stale"}]}), encoding="utf-8")
        self.assertEqual(run(T.main, str(voice), "--review", str(decisions))[0], 2)

    def test_input_errors(self):
        self.assertEqual(run(T.main, str(self.dir))[0], 2)
        other = self.dir / "x.pdf"
        other.write_text("x", encoding="utf-8")
        self.assertEqual(run(T.main, str(other))[0], 2)
        fake = self.dir / "fake.docx"
        fake.write_text("not a zip", encoding="utf-8")
        self.assertEqual(run(T.main, str(fake))[0], 2)


if __name__ == "__main__":
    unittest.main()
