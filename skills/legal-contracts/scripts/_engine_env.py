"""Run a contract script inside the engine's Python environment when the system python lacks its packages.

why: SKILL.md calls every script with plain `python3`, so the agent never has to find the engine's `.venv`.
A script whose third-party import fails re-runs itself once with `<engine>/.venv/bin/python` (built by
./install.sh); without that environment it stops with a clear message instead of a traceback.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# skills/legal-contracts/scripts/_engine_env.py → the engine root is three folders up (links resolved).
ENGINE_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = ENGINE_ROOT / ".venv" / "bin" / "python"
GUARD = "LEGAL_ENGINE_REEXEC"  # why: set on the re-run so a broken environment cannot loop forever


def reexec(script: str, missing: str, venv: Path = VENV_PYTHON) -> None:
    """Replace this process with the same script under the engine's Python; never returns on success."""
    if venv.is_file() and not os.environ.get(GUARD):
        os.environ[GUARD] = "1"
        os.execv(str(venv), [str(venv), str(Path(script).resolve()), *sys.argv[1:]])
    print(json.dumps({"error": f"Python package '{missing}' is missing: run ./install.sh in the engine folder "
                               f"({ENGINE_ROOT}) to build its environment"}, ensure_ascii=False))
    raise SystemExit(2)


def refuse_inside_engine(path: str | Path, error: type[Exception] = ValueError, root: Path = ENGINE_ROOT) -> Path:
    """why: a user's documents and reports belong in the matter folder of their profile, never in the engine
    repository, where a commit could publish them."""
    target = Path(path).expanduser().resolve()
    # why: compare by file identity, not by text — macOS folders ignore letter case, so a path typed in
    # another case would slip past a string comparison. The target may not exist yet: check its existing parents.
    probe = target
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    inside = any(_same(p, root) for p in (probe, *probe.parents))
    if inside:
        raise error(f"refusing to write inside the engine folder ({root}): write to the matter's output/ instead")
    return target


def _same(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def write_report(path: str | Path, text: str, inputs, error: type[Exception] = ValueError) -> Path:
    """Write a check report atomically: a `.json` file, never over one of the files checked, and over an existing
    file only when that file is itself JSON (an earlier report: reports in work/ are rewritten after each fix).
    why: `--report contract.md` replaced the contract, `--report signed.docx` would replace any document."""
    target = refuse_inside_engine(path, error)
    if target.suffix.lower() != ".json":
        raise error(f"a report is a .json file, got {path}")
    if target.exists():
        try:
            json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise error(f"refusing to replace {path}: it exists and is not an earlier JSON report") from exc
    for src in inputs:
        if src is not None and (_same(target, Path(src)) or target == Path(src).expanduser().resolve()):
            raise error(f"refusing to write the report over an input file: {src}")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)
    return target
