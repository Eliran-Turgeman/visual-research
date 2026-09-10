#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${MANIM_PYTHON:-python}"
if [[ -z "${MANIM_PYTHON:-}" && -x "$SCRIPT_DIR/../.venv/bin/python" ]]; then
  PYTHON="$SCRIPT_DIR/../.venv/bin/python"
fi
exec "$PYTHON" "$SCRIPT_DIR/render.py" "$@"
