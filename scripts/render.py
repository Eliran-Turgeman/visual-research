"""Thin, dependency-light entry point for manim_lib.production."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from manim_lib.production import main

if __name__ == "__main__":
    raise SystemExit(main())
