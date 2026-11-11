#!/usr/bin/env python3
"""Leak check of the public repository: no personal data, keys or the owner's private facts get out.

    python3 tools/check.py            # scan the repo; exit 1 on any FAIL
    python3 tools/check.py --quiet    # only the summary line and FAILs
    python3 tools/check.py --staged   # the exact staged content (the pre-commit hook), private paths refused

FAIL (blocks a commit and a push):
- an absolute home path (`/Users/<name>/`, `/home/<name>/`) other than the placeholders `you` / `user`;
- a key or token pattern;
- a 13-digit personal or company code (IDNP / IDNO in Moldova, CNP in Romania);
- an IBAN of Moldova or Romania;
- an e-mail address outside the example domains;
- a Moldovan or Romanian phone number;
- a word from the owner's local denylist (`tools/denylist.local.txt`, git-ignored: names of real firms,
  people and brands that must never be published);
- a private-block marker (`<!-` + `- private:`).
Text inside .docx files is scanned too (contracts are where real names hide), with their metadata (author,
last editor), comment and revision authors and link targets.
A line that must keep a pattern on purpose (a fake value in a test) carries `leak-ok`.
WARN (reported, does not block): decision numbers like `D` + 3 digits (private decision log), and a missing denylist.
"""

from __future__ import annotations

import argparse
import html
import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DENYLIST = ROOT / "tools" / "denylist.local.txt"

HOME_PATH = re.compile(r"/(?:Users|home)/(?!you/|user/|runner/|<)[A-Za-z0-9._-]+/")
SECRET = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_\w{20,}|AKIA[0-9A-Z]{16}|xox[abp]-\w{10,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY|fc-[a-f0-9]{32}|\b\d{8,10}:AA[\w-]{30,})"
)
CODE13 = re.compile(r"(?<!\d)\d{13}(?!\d)")
IBAN = re.compile(r"\b(?:MD|RO)\d{2}\s?[A-Z]{2,4}[A-Z0-9 ]{12,24}\b")
EMAIL = re.compile(r"\b[\w.+-]+@([\w-]+\.)+[A-Za-z]{2,}\b")
EMAIL_OK = re.compile(r"@(?:([\w-]+\.)*example\.(?:com|org|net)|anthropic\.com|users\.noreply\.github\.com)$")
PHONE = re.compile(r"(?:\+|\b00)(?:373|40)[\s.-]?\(?\d{2,3}\)?[\s.-]?\d{2,3}[\s.-]?\d{2,4}")
DECISION = re.compile(r"\bD\d{2,3}\b")
PRIVATE_MARK = "<!-" + "- private:"  # split: this file must not match itself
ALLOW = "leak-ok"

SKIP_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", "htmlcov"}
SKIP_PREFIXES = ("docs/owner/", ".agent/")  # why: both are git-ignored working notes
SKIP_FILES = {"tools/denylist.local.txt"}
TEXT_SUFFIXES = {".py", ".sh", ".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".html", ".css", ".js", ".xml",
                 ".cfg", ".ini", ""}


def load_denylist(path: Path = DENYLIST) -> list[str]:
    if not path.is_file():
        return []
    words = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        word = raw.strip()
        if word and not word.startswith("#"):
            words.append(word.casefold())
    return words


def files(base: Path) -> list[Path]:
    out = []
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(base).as_posix()
        if SKIP_PARTS & set(p.relative_to(base).parts) or rel.startswith(SKIP_PREFIXES) or rel in SKIP_FILES:
            continue
        out.append(p)
    return out


# why: a name can sit only in metadata or attributes: the author of a comment or a tracked change (w:author),
# the document's creator (docProps), or a link target (mailto:, a personal site) in the relationships.
DOCX_ATTRS = re.compile(r'\b(?:w:author|w:initials|Target)="([^"]*)"')


def docx_text(path: Path | bytes) -> str:
    """Text of a .docx for the scan: visible text (body, headers, footers, comments), one paragraph per line,
    then metadata, authors and link targets."""
    name = path.name if isinstance(path, Path) else "file"
    try:
        with zipfile.ZipFile(path if isinstance(path, Path) else io.BytesIO(path)) as z:
            embedded = [n for n in z.namelist() if n.startswith("word/embeddings/")]
            if embedded:
                # an embedded workbook or document is a file of its own that this scan cannot read
                raise ValueError(f"{name}: embedded objects are not scanned ({', '.join(embedded[:3])}); remove them")
            parts = [n for n in z.namelist() if n.endswith((".xml", ".rels"))
                     and (n.startswith(("word/", "docProps/", "customXml/")) or n == "_rels/.rels")]
            xml = "\n".join(z.read(n).decode("utf-8", errors="replace") for n in parts)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{name}: not a valid .docx ({exc})") from exc
    attrs = "\n".join(m.group(1) for m in DOCX_ATTRS.finditer(xml))
    text = re.sub(r"</w:p>|</(?:dc|cp|dcterms):[^>]+>", "\n", xml)
    # why: XML stores "&" as "&amp;": a denylisted "Example & Partners" must match after decoding
    return html.unescape(re.sub(r"<[^>]+>", "", text) + "\n" + attrs)


def scan_lines(rel: str, text: str, deny: list[str]) -> tuple[list[str], list[str]]:
    fails, warns = [], []
    for n, line in enumerate(text.splitlines(), 1):
        where = f"{rel}:{n}"
        if PRIVATE_MARK in line:
            fails.append(f"{where}: остался маркер private")
        if ALLOW in line:
            continue
        if HOME_PATH.search(line):
            fails.append(f"{where}: абсолютный домашний путь")
        if SECRET.search(line):
            fails.append(f"{where}: похоже на ключ или токен")
        if CODE13.search(line):
            fails.append(f"{where}: 13-значный код (IDNP / IDNO / CNP)")
        if IBAN.search(line):
            fails.append(f"{where}: похоже на IBAN")
        for m in EMAIL.finditer(line):
            if not EMAIL_OK.search(m.group(0)):
                fails.append(f"{where}: e-mail {m.group(0)}")
        if PHONE.search(line):
            fails.append(f"{where}: номер телефона")
        low = line.casefold()
        # why: whole words only, so a surname does not fire inside a public login or another word.
        if any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", low) for word in deny):
            fails.append(f"{where}: слово из denylist")
        if DECISION.search(line):
            warns.append(f"{where}: номер решения {DECISION.search(line).group(0)} (личный журнал?)")
    return fails, warns


def scan_file(rel: str, data: bytes, deny: list[str]) -> tuple[list[str], list[str]]:
    name = rel.rsplit("/", 1)[-1]
    if name == ".env" or name.startswith(".env."):
        return [f"{rel}: файл .env в репозитории"], []
    suffix = Path(rel).suffix
    if suffix == ".docx":
        try:
            text = docx_text(data)
        except ValueError as exc:
            return [f"{rel}: {exc}"], []
    elif suffix in TEXT_SUFFIXES:
        text = data.decode("utf-8", errors="replace")
    else:
        return [], []
    return scan_lines(rel, text, deny)


def scan(base: Path = ROOT, deny: list[str] | None = None) -> tuple[list[str], list[str]]:
    """(fails, warns) for every file under `base`; paths are shown relative to `base`."""
    deny = load_denylist() if deny is None else deny
    fails: list[str] = []
    warns: list[str] = [] if deny else ["нет tools/denylist.local.txt: имена реальных фирм и людей не проверены"]
    for path in files(base):
        f, w = scan_file(path.relative_to(base).as_posix(), path.read_bytes(), deny)
        fails += f
        warns += w
    return fails, warns


def _git(base: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(base), *args], capture_output=True, check=True).stdout


def scan_staged(base: Path = ROOT, deny: list[str] | None = None) -> tuple[list[str], list[str], int]:
    """(fails, warns, files) for the content staged for the commit, read from the index, not the working tree.
    why: a file staged with personal data and cleaned only in the working tree would pass a working-tree scan."""
    deny = load_denylist() if deny is None else deny
    fails: list[str] = []
    warns: list[str] = [] if deny else ["нет tools/denylist.local.txt: имена реальных фирм и людей не проверены"]
    names = [n for n in _git(base, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
             .decode("utf-8").split("\0") if n]
    for rel in names:
        parts = set(Path(rel).parts)
        if (rel.startswith(SKIP_PREFIXES + ("legal-profile/",)) or rel in SKIP_FILES
                or parts & {".venv", ".coverage", "legal-profile"}):
            # git-ignored private paths, force-added or not: never committed
            fails.append(f"{rel}: личный файл (git-ignored) добавлен в коммит")
            continue
        f, w = scan_file(rel, _git(base, "show", f":{rel}"), deny)
        fails += f
        warns += w
    return fails, warns, len(names)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quiet", action="store_true", help="без списка предупреждений")
    ap.add_argument("--staged", action="store_true", help="проверить то, что добавлено в коммит (git index)")
    a = ap.parse_args(argv)
    if a.staged:
        fails, warns, n = scan_staged()
    else:
        fails, warns = scan()
        n = len(files(ROOT))
    for line in fails:
        print("FAIL ", line)
    if not a.quiet:
        for line in warns:
            print("WARN ", line)
    print(f"check: {len(fails)} FAIL, {len(warns)} WARN, файлов {n}")
    return 1 if fails else 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):  # why: a Windows pipe defaults to the ANSI code page (no ș, ț, Cyrillic)
        getattr(_stream, "reconfigure", lambda **_: None)(encoding="utf-8")
    sys.exit(main())
