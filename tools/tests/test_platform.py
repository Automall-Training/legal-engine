"""Rules that keep the engine working on Windows as well as on macOS and Linux (scans the repo's own files)."""

from __future__ import annotations

import ast
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP = {".git", ".venv", "__pycache__"}


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def python_files() -> list[Path]:
    return [p for p in sorted(ROOT.rglob("*.py")) if not SKIP & set(p.relative_to(ROOT).parts)]


def _mode(call: ast.Call, positional: list[ast.expr]) -> object:
    for kw in call.keywords:
        if kw.arg == "mode":
            return kw.value.value if isinstance(kw.value, ast.Constant) else "?"
    if positional:
        return positional[0].value if isinstance(positional[0], ast.Constant) else "?"
    return "r"


def text_io_without_encoding(tree: ast.AST) -> list[int]:
    """Lines that read or write text without `encoding=`.
    why: without it Python uses the system code page, cp1251 / cp1252 on Windows, which garbles or rejects
    Cyrillic and Romanian letters; a binary mode ("rb", "wb", …) has no encoding and is allowed."""
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        if name not in ("open", "read_text", "write_text", "fdopen"):
            continue
        if any(kw.arg == "encoding" for kw in node.keywords):
            continue
        if name == "open":
            # open(path, mode) as a function; path.open(mode) as a method
            mode = _mode(node, node.args[1:] if isinstance(f, ast.Name) else node.args)
        elif name == "fdopen":
            mode = _mode(node, node.args[1:])
        else:
            mode = "r"
        if isinstance(mode, str) and "b" in mode:
            continue
        bad.append(node.lineno)
    return bad


class TextEncoding(unittest.TestCase):
    def test_scanner_finds_and_allows(self):
        src = ("open(p)\nopen(p, 'rb')\nopen(p, 'w', encoding='utf-8')\np.read_text()\np.write_text(t, encoding='utf-8')\n"
               "p.open('rb')\np.open()\nos.fdopen(fd, 'w')\np.read_bytes()\n")
        self.assertEqual(text_io_without_encoding(ast.parse(src)), [1, 4, 7, 8])

    def test_every_text_file_access_names_its_encoding(self):
        bad = [f"{p.relative_to(ROOT).as_posix()}:{line}" for p in python_files()
               for line in text_io_without_encoding(ast.parse(p.read_text(encoding="utf-8")))]
        self.assertEqual(bad, [], "add encoding=\"utf-8\" (Windows would use its ANSI code page)")

    def test_command_line_scripts_print_utf8(self):
        """why: a Windows pipe (the agent reading a script's output) defaults to the ANSI code page, so a script
        printing ș, ț or Cyrillic would crash with UnicodeEncodeError unless it switches its streams to UTF-8."""
        scripts = [p for p in python_files() if "tests" not in p.parts
                   and re.search(r"^if __name__ *== *['\"]__main__['\"]", p.read_text(encoding="utf-8"), re.M)]
        self.assertGreaterEqual(len(scripts), 10)
        missing = [p.relative_to(ROOT).as_posix() for p in scripts
                   if 'reconfigure", lambda **_: None)(encoding="utf-8")' not in p.read_text(encoding="utf-8")]
        self.assertEqual(missing, [])


class EnginePython(unittest.TestCase):
    """legal-watch keeps its own copy of the engine-Python rule (skills do not import each other's packages)."""

    def test_both_copies_agree(self):
        env = load("_engine_env", ROOT / "skills/legal-contracts/scripts/_engine_env.py")
        sys.path.insert(0, str(ROOT / "skills/legal-watch/scripts"))
        try:
            from watch import schedule
        finally:
            sys.path.remove(str(ROOT / "skills/legal-watch/scripts"))
        for windows in (True, False):
            self.assertEqual(env.venv_python(ROOT, windows), schedule.venv_python(ROOT, windows))
        self.assertEqual(env.WINDOWS, schedule.WINDOWS)

    def test_no_hard_coded_posix_interpreter_in_code(self):
        """Only the helpers (and comments or messages naming both layouts) may spell `.venv/bin/python`."""
        allowed = {"skills/legal-contracts/scripts/_engine_env.py", "skills/legal-watch/scripts/watch/schedule.py"}
        offenders = []
        for p in python_files():
            rel = p.relative_to(ROOT).as_posix()
            if rel in allowed or "tests" in p.parts:
                continue
            lines = p.read_text(encoding="utf-8").splitlines()
            for n, line in enumerate(lines, 1):
                code = line.split("#", 1)[0]
                # a message may name both layouts across two source lines
                both = "python.exe" in code + (lines[n] if n < len(lines) else "")
                if re.search(r"""["']bin["']\s*/\s*["']python["']|\.venv/bin/python""", code) and not both:
                    offenders.append(f"{rel}:{n}")
        self.assertEqual(offenders, [])


class SymlinksInTests(unittest.TestCase):
    def test_every_test_making_symlinks_checks_it_may(self):
        """why: ordinary Windows (no admin, no Developer Mode) refuses symlinks; a test module that makes one must
        probe first (CAN_SYMLINK) and skip, or use a junction for a directory."""
        bad = [p.relative_to(ROOT).as_posix() for p in python_files() if "tests" in p.parts
               and re.search(r"symlink_to\(|os\.symlink\(", p.read_text(encoding="utf-8"))
               and "CAN_SYMLINK" not in p.read_text(encoding="utf-8")]
        self.assertEqual(bad, [])


def git_bash() -> str | None:
    """The bash that runs git hooks, or None.
    why: on Windows `bash` on PATH may be C:\\Windows\\System32\\bash.exe, the WSL launcher (no Linux inside,
    UTF-16 output); git hooks run in Git for Windows' own bash, found next to `git --exec-path`."""
    if os.name != "nt":
        return shutil.which("bash")
    try:
        exec_path = subprocess.run(["git", "--exec-path"], capture_output=True, text=True, encoding="utf-8",
                                   check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        exec_path = ""
    for base in Path(exec_path).parents if exec_path else ():
        for cand in (base / "bin" / "bash.exe", base / "usr" / "bin" / "bash.exe"):
            if cand.is_file():
                return str(cand)
    found = shutil.which("bash")
    if found and "system32" not in found.lower() and "windowsapps" not in found.lower():
        return found
    return None


class PreCommitHook(unittest.TestCase):
    def test_store_placeholder_python3_is_skipped(self):
        """why: Windows' `python3` may be the Microsoft Store placeholder: it exists, but only opens the Store."""
        bash = git_bash()
        if not bash:
            self.skipTest("needs the bash git runs hooks with (Git Bash on Windows)")
        hook = (ROOT / "tools/hooks/pre-commit").read_text(encoding="utf-8")
        probe = hook[hook.index("PY3=\n"):hook.index('if [ -z "$PY3" ]')]
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            fake = bin_dir / "python3"
            fake.write_text("#!/bin/sh\nexit 49\n", encoding="utf-8", newline="\n")
            fake.chmod(0o755)
            real = bin_dir / "python"
            real.write_text(f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" "$@"\n', encoding="utf-8",
                            newline="\n")
            real.chmod(0o755)
            # why: PATH is set inside bash: Git Bash wants /c/... folders, which cygpath gives (absent elsewhere)
            script = (f'D="{bin_dir.as_posix()}"; command -v cygpath >/dev/null 2>&1 && D="$(cygpath -u "$D")"\n'
                      f'PATH="$D:/usr/bin:/bin"\nROOT="$D/none"\n{probe}printf %s "$PY3"\n')
            out = subprocess.run([bash, "-c", script], capture_output=True, text=True, encoding="utf-8",
                                 errors="replace")
        self.assertEqual(out.stdout, "python", out.stderr)


class Installers(unittest.TestCase):
    def test_powershell_installer_matches_the_bash_one(self):
        ps = (ROOT / "install.ps1").read_bytes()
        # why: Windows PowerShell 5.1 reads a script without a BOM in the ANSI code page: «настрой юриста» would break
        self.assertTrue(ps.startswith(b"\xef\xbb\xbf"), "install.ps1 must be saved as UTF-8 with BOM")
        text = ps.decode("utf-8-sig")
        sh = (ROOT / "install.sh").read_text(encoding="utf-8")
        for word in ("link   ", "(updated)", "SKIP   ", "env    .venv (Python 3.12)", "env    packages",
                     "browser Playwright Chromium", "MISS   uv", "FAIL   ", "next   ", "настрой юриста",
                     "requirements.txt", "--python 3.12", "NO_DEPS", "WITH_PLAYWRIGHT", "SKILLS_DIR", "doctor.py"):
            self.assertIn(word, sh, word)
            self.assertIn(word, text, word)
        self.assertIn("Junction", text)
        self.assertIn(r".claude\skills", text)          # same default skills folder as install.sh
        self.assertIn(r".venv\Scripts\python.exe", text)


if __name__ == "__main__":
    unittest.main()
