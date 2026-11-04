#!/usr/bin/env bash
# Install the legal engine on this computer (idempotent; never deletes or overwrites a real folder).
#   ./install.sh                     # links skills/* into ~/.claude/skills, Python environment, doctor
#   SKILLS_DIR=… ./install.sh        # another skills folder (e.g. a project's .claude/skills)
#   NO_DEPS=1 ./install.sh           # links only: no Python environment
#   WITH_PLAYWRIGHT=1 ./install.sh   # also the free browser engine for scheduled law monitoring
set -euo pipefail
ENGINE="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="${SKILLS_DIR:-$HOME/.claude/skills}"
export SKILLS_DIR
mkdir -p "$SKILLS_DIR"

for src in "$ENGINE"/skills/*/; do
  [ -f "$src/SKILL.md" ] || continue
  name="$(basename "$src")"; dst="$SKILLS_DIR/$name"
  if [ -L "$dst" ]; then
    ln -sfn "${src%/}" "$dst"; echo "link   $name (updated)"
  elif [ -e "$dst" ]; then
    echo "SKIP   $name: $dst is a real folder — move it away yourself, then run again"
  else
    ln -s "${src%/}" "$dst"; echo "link   $name"
  fi
done

if [ -z "${NO_DEPS:-}" ]; then
  if command -v uv >/dev/null 2>&1; then
    if [ ! -x "$ENGINE/.venv/bin/python" ]; then
      uv venv -q --python 3.12 "$ENGINE/.venv" && echo "env    .venv (Python 3.12)"
    fi
    uv pip install -q --python "$ENGINE/.venv/bin/python" -r "$ENGINE/requirements.txt" && echo "env    packages"
    if [ -n "${WITH_PLAYWRIGHT:-}" ]; then
      uv pip install -q --python "$ENGINE/.venv/bin/python" playwright \
        && "$ENGINE/.venv/bin/python" -m playwright install chromium && echo "browser Playwright Chromium"
    fi
  else
    echo "MISS   uv — install it (https://docs.astral.sh/uv/), then run ./install.sh again"
  fi
fi

python3 "$ENGINE/tools/doctor.py" || true
echo "next   open Claude Code and say: «настрой юриста» / «configurează juristul» / «set up the lawyer»"
