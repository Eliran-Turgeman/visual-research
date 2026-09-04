#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 SCENE_FILE SCENE_NAME" >&2
  exit 2
fi

QUALITY="${MANIM_QUALITY:--qh}"
python -m manim "$QUALITY" "$1" "$2"
