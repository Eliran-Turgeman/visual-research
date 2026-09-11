#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROBE='import sys; sys.exit(not ((3, 11) <= sys.version_info[:2] < (3, 14)))'
REQUESTED_PYTHON=""
next_python=false
for arg in "$@"; do
  if "$next_python"; then REQUESTED_PYTHON="$arg"; next_python=false; fi
  case "$arg" in
    --python) next_python=true ;;
    --python=*) REQUESTED_PYTHON="${arg#--python=}" ;;
  esac
done
for python in "$REQUESTED_PYTHON" "$SCRIPT_DIR/../.venv/bin/python" \
    "$SCRIPT_DIR/../.venv/Scripts/python.exe" \
    python3.12 python3.11 python3.13 python3 python; do
  if command -v "$python" >/dev/null 2>&1 && "$python" -I -c "$PROBE" >/dev/null 2>&1; then
    exec "$python" "$SCRIPT_DIR/setup.py" "$@"
  fi
done

if command -v uv >/dev/null 2>&1; then
  uv python install --no-bin --no-registry 3.12
  python="$(uv python find --no-project --system 3.12)"
  exec "$python" "$SCRIPT_DIR/setup.py" "$@"
fi

printf '%s\n' \
  "Python 3.11-3.13 or uv is required. Install a supported Python using your OS package manager." \
  "macOS: brew install python@3.12 (or brew install uv)." \
  "Debian/Ubuntu: sudo apt install python3 python3-venv (check Python is 3.11-3.13)." \
  "See https://docs.astral.sh/uv/getting-started/installation/ for packaged uv options." >&2
exit 1
