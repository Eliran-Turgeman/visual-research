"""Thin, dependency-light entry point for manim_lib.production.

Run the module by path so --help and missing-dependency errors do not first
import manim_lib's eager visual-component exports.
"""

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "manim_lib" / "production.py"),
        run_name="__main__",
    )
