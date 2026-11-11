#!/usr/bin/env python3
"""Check that this computer can run the legal engine (stdlib only, read-only).

    python3 tools/doctor.py     # report; exit 0 = all required parts present, 1 = something required is missing

Required: every engine skill linked into the skills folder, python3 >= 3.10, the engine's Python
environment (.venv with the document packages: `.venv/bin/python` on Mac/Linux, `.venv\\Scripts\\python.exe` on
Windows). Optional parts are reported with what they serve.
The user's profile is reported, not required: the setup wizard creates it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# why: the profile contract belongs to the legal-workflow skill and the engine's Python to legal-contracts;
# doctor reuses both instead of keeping copies.
sys.path.insert(0, str(ROOT / "skills" / "legal-workflow" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "legal-contracts" / "scripts"))
import _engine_env  # noqa: E402
import legal_profile  # noqa: E402
SKILLS_DIR = Path(os.environ.get("SKILLS_DIR", Path.home() / ".claude" / "skills"))
CONFIG = legal_profile.CONFIG
DEFAULT_PROFILE = legal_profile.DEFAULT_PROFILE
VENV_PY = _engine_env.venv_python(ROOT)
INSTALL = _engine_env.install_hint()
# why: import names differ from package names (python-docx → docx, PyYAML → yaml).
VENV_IMPORTS = ("docx", "lxml", "pypdf", "pdfplumber", "yaml")
OPTIONAL_CMDS = {
    "soffice": "LibreOffice: render DOCX to PDF for a visual check (or use Word)",
    "pdftoppm": "Poppler: PDF pages to images for the visual check",
    "tesseract": "OCR of scanned contracts (needs the ron / rus / eng language packs)",
    "uv": f"{INSTALL} builds the Python environment with it",
}
# where Playwright keeps its browsers: macOS, Linux, Windows (%LOCALAPPDATA%)
PLAYWRIGHT_CACHES = (Path.home() / "Library/Caches/ms-playwright", Path.home() / ".cache/ms-playwright",
                     Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "ms-playwright")


def engine_skills(root: Path = ROOT) -> list[str]:
    base = root / "skills"
    return sorted(p.name for p in base.iterdir() if (p / "SKILL.md").is_file()) if base.is_dir() else []


def profile_dir(config: Path = CONFIG) -> tuple[Path, str]:
    """(profile folder, where the path came from). A broken config is reported, never guessed around."""
    try:
        return legal_profile.resolve_profile(config)
    except legal_profile.LegalProfileError as exc:
        raise SystemExit(str(exc)) from exc


def line(ok: bool | None, what: str, note: str = "") -> None:
    tag = {True: "OK  ", False: "MISS", None: "--  "}[ok]
    print(f"{tag} {what}" + (f" — {note}" if note else ""))


def skill_source(dst: Path, src: Path) -> str:
    """How an installed skill folder relates to this engine's copy of it.
    why: install.sh makes a symlink, install.ps1 a directory junction (no admin rights needed), and some people
    copy the folder by hand; `resolve()` follows both kinds of link, so the test does not ask which one it is."""
    if not (dst / "SKILL.md").is_file():
        return "missing"
    if dst.resolve() == src.resolve():
        return "this repo"
    try:
        same = (dst / "SKILL.md").read_bytes() == (src / "SKILL.md").read_bytes()
    except OSError:
        same = False
    return f"a copy of this repo (run {INSTALL} again after each update)" if same else "another copy"


def venv_ready(py: Path = VENV_PY) -> bool:
    if not py.is_file():
        return False
    code = "import " + ", ".join(VENV_IMPORTS)
    return subprocess.run([str(py), "-c", code], capture_output=True).returncode == 0


def playwright_ready(py: Path = VENV_PY, caches: tuple[Path, ...] = PLAYWRIGHT_CACHES) -> bool:
    """The browser engine runs only with both parts: the Python package in .venv and a downloaded Chromium.
    why: a Chromium left by another tool in the shared cache made doctor say OK while the engine failed to import."""
    chromium = any(c.is_dir() and any(c.glob("chromium*")) for c in caches)
    if not (chromium and py.is_file()):
        return False
    return subprocess.run([str(py), "-c", "import playwright"], capture_output=True).returncode == 0


def playwright_hint(windows: bool | None = None) -> str:
    windows = _engine_env.WINDOWS if windows is None else windows
    return f"$env:WITH_PLAYWRIGHT=1; {INSTALL}" if windows else f"WITH_PLAYWRIGHT=1 {INSTALL}"


def open_watch_issues(profile: Path) -> int:
    """Open problems in the monitoring error log (legal-watch issues.json); 0 when there is none or it is broken."""
    try:
        log = json.loads((profile / "laws" / "issues.json").read_text(encoding="utf-8"))
        return sum(1 for e in (log.get("acts") or {}).values() if e.get("state") == "open")
    except (OSError, ValueError, AttributeError):
        return 0


def engine_version(root: Path = ROOT) -> str:
    """Name and version from VENDOR.json, so a bug report can say which release is installed."""
    try:
        v = json.loads((root / "VENDOR.json").read_text(encoding="utf-8"))
        return f"{v['name']} {v['version']} ({v['released']})"
    except (OSError, ValueError, KeyError, TypeError):
        return "unknown version (VENDOR.json missing or unreadable)"


def main() -> int:
    missing = 0
    print(f"engine: {engine_version()}")
    print(f"skills folder: {SKILLS_DIR}")
    skills = engine_skills()
    if not skills:
        line(None, "engine skills", "none in this repo yet")
    for name in skills:
        source = skill_source(SKILLS_DIR / name, ROOT / "skills" / name)
        ok = source != "missing"
        line(ok, f"skill {name}", source if ok else f"run {INSTALL}")
        missing += not ok
    py_ok = sys.version_info >= (3, 10)
    line(py_ok, f"python3 {sys.version.split()[0]}", "3.10 or newer")
    missing += not py_ok
    env_ok = venv_ready()
    line(env_ok, "Python environment .venv (python-docx, lxml, pypdf, pdfplumber, PyYAML)",
         "" if env_ok else f"run {INSTALL}")
    missing += not env_ok
    for cmd, why in OPTIONAL_CMDS.items():
        line(True if shutil.which(cmd) else None, cmd, why)
    browser = playwright_ready()
    line(True if browser else None, "Playwright Chromium",
         "free engine for scheduled law monitoring; " + playwright_hint())
    prof, source = profile_dir()
    ready = (prof / "context" / "integration-status.md").is_file()
    line(True if ready else None, f"profile {prof}", source if ready else f"{source}; the setup wizard creates it")
    n = open_watch_issues(prof)
    if n:   # informational: a site that refuses access does not make the engine "not ready"
        line(None, f"law monitoring: {n} open problem(s)", f"see {prof / 'laws' / 'report.html'}")
    print("READY" if not missing else f"NOT READY: {missing} required part(s) missing")
    return 0 if not missing else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # why: a Windows pipe defaults to the ANSI code page (no ș, ț, Cyrillic)
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8")
    sys.exit(main())
