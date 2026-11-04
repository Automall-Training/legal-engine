#!/usr/bin/env python3
"""Check that this computer can run the legal engine (stdlib only, read-only).

    python3 tools/doctor.py     # report; exit 0 = all required parts present, 1 = something required is missing

Required: every engine skill linked into the skills folder, python3 >= 3.10, the engine's Python
environment (.venv with the document packages). Optional parts are reported with what they serve.
The user's profile is reported, not required: the setup wizard creates it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# why: the profile contract belongs to the legal-workflow skill; doctor reuses its lookup instead of a copy.
sys.path.insert(0, str(ROOT / "skills" / "legal-workflow" / "scripts"))
import legal_profile  # noqa: E402
SKILLS_DIR = Path(os.environ.get("SKILLS_DIR", Path.home() / ".claude" / "skills"))
CONFIG = Path(os.environ.get("LEGAL_ENGINE_CONFIG", Path.home() / ".config" / "legal-engine" / "config.json"))
DEFAULT_PROFILE = legal_profile.DEFAULT_PROFILE
VENV_PY = ROOT / ".venv" / "bin" / "python"
# why: import names differ from package names (python-docx → docx, PyYAML → yaml).
VENV_IMPORTS = ("docx", "lxml", "pypdf", "pdfplumber", "yaml")
OPTIONAL_CMDS = {
    "soffice": "LibreOffice: render DOCX to PDF for a visual check (or use Word)",
    "pdftoppm": "Poppler: PDF pages to images for the visual check",
    "tesseract": "OCR of scanned contracts (needs the ron / rus / eng language packs)",
    "uv": "./install.sh builds the Python environment with it",
}
PLAYWRIGHT_CACHES = (Path.home() / "Library/Caches/ms-playwright", Path.home() / ".cache/ms-playwright")


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


def venv_ready(py: Path = VENV_PY) -> bool:
    if not py.is_file():
        return False
    code = "import " + ", ".join(VENV_IMPORTS)
    return subprocess.run([str(py), "-c", code], capture_output=True).returncode == 0


def main() -> int:
    missing = 0
    print(f"skills folder: {SKILLS_DIR}")
    skills = engine_skills()
    if not skills:
        line(None, "engine skills", "none in this repo yet")
    for name in skills:
        dst = SKILLS_DIR / name
        ok = (dst / "SKILL.md").is_file()
        own = dst.is_symlink() and dst.resolve() == (ROOT / "skills" / name).resolve()
        line(ok, f"skill {name}", "this repo" if own else ("another copy" if ok else "run ./install.sh"))
        missing += not ok
    py_ok = sys.version_info >= (3, 10)
    line(py_ok, f"python3 {sys.version.split()[0]}", "3.10 or newer")
    missing += not py_ok
    env_ok = venv_ready()
    line(env_ok, "Python environment .venv (python-docx, lxml, pypdf, pdfplumber, PyYAML)",
         "" if env_ok else "run ./install.sh")
    missing += not env_ok
    for cmd, why in OPTIONAL_CMDS.items():
        line(True if shutil.which(cmd) else None, cmd, why)
    chromium = any(c.is_dir() and any(c.glob("chromium*")) for c in PLAYWRIGHT_CACHES)
    line(True if chromium else None, "Playwright Chromium",
         "free engine for scheduled law monitoring; WITH_PLAYWRIGHT=1 ./install.sh")
    prof, source = profile_dir()
    ready = (prof / "context" / "integration-status.md").is_file()
    line(True if ready else None, f"profile {prof}", source if ready else f"{source}; the setup wizard creates it")
    print("READY" if not missing else f"NOT READY: {missing} required part(s) missing")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
