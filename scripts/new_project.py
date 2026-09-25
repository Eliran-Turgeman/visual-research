"""Start a fresh video workspace without copying an existing visual solution."""

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SKILL = "technical-manim-explainer"


def create(destination: Path, brief: Path | None = None, *, root: Path = ROOT) -> Path:
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("Destination already exists; choose a new directory.")
    destination = destination.resolve()
    if destination.is_relative_to(root.resolve()):
        raise ValueError("Choose a fresh workspace outside this repository.")
    if any((parent / ".git").exists() for parent in destination.parents):
        raise ValueError("Choose a workspace outside existing Git checkouts.")
    if not destination.parent.is_dir():
        raise ValueError("The destination's parent directory must exist.")
    files = {
        Path(name): (root / name).read_bytes()
        for name in ("pyproject.toml", "uv.lock", ".python-version", ".gitignore")
    }
    for name in ("SKILL.md", "MANIM_GUIDE.md"):
        files[Path(".github") / "skills" / SKILL / name] = (
            root / "skills" / SKILL / name
        ).read_bytes()
    for name in ("narrate.py", "frames.py"):
        files[Path("scripts") / name] = (root / "scripts" / name).read_bytes()
    files[Path("AGENTS.md")] = (
        f"Read `.github/skills/{SKILL}/SKILL.md` and `brief.md`.\n"
        "Use native Manim and scene-local helpers; invent the visual representation.\n"
        "Setup: `uv sync --locked --no-dev`. Render with native `python -m manim`.\n"
        "Utilities: `scripts/narrate.py` and `scripts/frames.py` (see --help).\n"
        "Speech requests need explicit --generate. Never persist credentials.\n"
        "Do not use other animation skills, libraries, or existing scene templates.\n"
    ).encode()
    content = (
        brief.expanduser().read_bytes() if brief else
        b"# Video brief\n\nTopic:\nAudience:\nSources:\nLength:\nNarration: MAI-Voice-2 / Harper\n"
    )
    if not content.decode("utf-8-sig").strip():
        raise ValueError("The brief must contain nonblank UTF-8 text.")
    files[Path("brief.md")] = content
    destination.mkdir()
    for relative, content in files.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--brief", type=Path, help="UTF-8 brief; otherwise create a blank template")
    args = parser.parse_args(argv)
    try:
        destination = create(args.destination, args.brief)
    except (OSError, ValueError) as exc:
        print(f"Cannot create workspace: {exc}\nPartial files, if any, were left in place.", file=sys.stderr)
        return 1
    print(f"Created {destination}\nRun uv sync --locked --no-dev there, then start a fresh agent session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
