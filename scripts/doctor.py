"""Run the installation doctor without importing Manim-dependent package exports."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "manim_lib" / "doctor.py"),
        run_name="__main__",
    )
