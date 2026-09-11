"""Install into this checkout's .venv without activation or global package changes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RECOMMENDED_PYTHON = "3.12"
PROVIDER_EXTRAS = {
    "none": None,
    "openrouter": "voiceover-openrouter",
    "gtts": "voiceover-gtts",
    "external-gtts": "voiceover-gtts",
    "openai": "voiceover-openai",
    "azure": "voiceover-azure",
}
PYTHON_PROBE = (
    "import json,sys; print(json.dumps({"
    "'version':list(sys.version_info[:3]),"
    "'prefix':sys.prefix,'base_prefix':sys.base_prefix}))"
)
PIP_PROBE = (
    "import importlib.util; "
    "print('present' if importlib.util.find_spec('pip') is not None else 'missing')"
)


class SetupError(Exception):
    def __init__(self, message: str, returncode: int = 1):
        super().__init__(message)
        self.returncode = returncode if returncode > 0 else 1


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Defaults: base dependencies and credential-free silent doctor checks. "
            "uv uses the committed lock; pip performs an editable, unlocked install. "
            "An existing compatible .venv is reused, never deleted. Native libraries "
            "and LaTeX remain manual/opt-in. No activation is needed afterwards: "
            "use scripts/render.ps1 or scripts/render.sh."
        ),
    )
    result.add_argument(
        "--installer", choices=("auto", "uv", "pip"), default="auto",
        help="auto prefers installed uv; uses pip only when uv is unavailable",
    )
    result.add_argument(
        "--provider", choices=tuple(PROVIDER_EXTRAS), default="none",
        help="install only this provider's optional dependencies (default: none)",
    )
    result.add_argument("--dev", action="store_true", help="include the dev extra")
    result.add_argument(
        "--python", metavar="INTERPRETER",
        help="3.11, 3.12, 3.13, or a Python executable path/name; must match an existing .venv",
    )
    return result


def child_environment(venv: Path) -> dict[str, str]:
    env = os.environ.copy()
    # Never let the caller's active environment or pip destination redirect setup.
    for name in (
        "VIRTUAL_ENV", "CONDA_PREFIX", "PYTHONHOME", "PYTHONPATH",
        "PIP_TARGET", "PIP_PREFIX", "PIP_USER", "PIP_PYTHON",
        "UV_PROJECT", "UV_WORKING_DIRECTORY", "UV_PYTHON",
    ):
        env.pop(name, None)
    env["UV_PROJECT_ENVIRONMENT"] = str(venv)
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_REQUIRE_VIRTUALENV"] = "true"
    return env


def run(
    command: list[str], root: Path, env: dict[str, str], *, capture: bool = False,
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command, cwd=root, env=env, text=True, check=False,
            capture_output=capture,
        )
    except OSError as exc:
        raise SetupError(f"Cannot run {command[0]!r}: {exc}") from exc


def checked(command: list[str], root: Path, env: dict[str, str]) -> None:
    result = run(command, root, env)
    if result.returncode:
        raise SetupError(
            f"Command failed (exit {result.returncode}): {subprocess.list2cmdline(command)}",
            result.returncode,
        )


def probe(python: str, root: Path, env: dict[str, str]) -> dict:
    result = run([python, "-I", "-c", PYTHON_PROBE], root, env, capture=True)
    try:
        info = json.loads(result.stdout)
        version = tuple(info["version"])
        if result.returncode or not (3, 11) <= version[:2] < (3, 14):
            raise ValueError
        if not info["prefix"] or not info["base_prefix"]:
            raise ValueError
    except (ValueError, KeyError, TypeError) as exc:
        raise SetupError(
            f"{python!r} is not a working Python >=3.11,<3.14. "
            "Install Python 3.12, or choose a compatible executable with --python."
        ) from exc
    return info


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def existing_python(venv: Path, root: Path, env: dict[str, str]) -> tuple[str, dict] | None:
    if not venv.exists() and not venv.is_symlink():
        return None
    remedy = (
        f"Existing environment {venv} was left unchanged. "
        "Move it aside manually and rerun setup, or use a separate checkout."
    )
    if venv.resolve() != venv.absolute() or not (venv / "pyvenv.cfg").is_file():
        raise SetupError(f".venv must be a local, isolated virtual environment. {remedy}")
    config = (venv / "pyvenv.cfg").read_text(encoding="utf-8").lower()
    for line in config.splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "include-system-site-packages" and value.strip() == "true":
            raise SetupError(f".venv exposes system site packages. {remedy}")
    python = str(venv_python(venv))
    try:
        info = probe(python, root, env)
    except SetupError as exc:
        raise SetupError(f"{exc} {remedy}") from exc
    if (
        Path(info["prefix"]).resolve() != venv.resolve()
        or info["prefix"] == info["base_prefix"]
    ):
        raise SetupError(f".venv's Python does not belong to this environment. {remedy}")
    return python, info


def selector_version(selector: str | None) -> tuple[int, int] | None:
    if selector and all(part.isdigit() for part in selector.split(".")):
        if selector not in ("3.11", "3.12", "3.13"):
            raise SetupError("Supported --python versions are 3.11, 3.12 and 3.13.")
        return tuple(int(part) for part in selector.split("."))
    return None


def executable(selector: str) -> str:
    path = Path(selector).expanduser()
    if path.is_file():
        return str(path.resolve())
    found = shutil.which(selector)
    if found:
        return found
    raise SetupError(
        f"Python executable {selector!r} was not found. "
        "Use --python with an existing executable, or a supported version such as 3.12."
    )


def choose_python(
    selector: str | None, uv: str | None, root: Path, env: dict[str, str],
) -> str:
    version = selector_version(selector)
    if selector and version is None:
        python = executable(selector)
        probe(python, root, env)
        return python
    candidates = [sys.executable]
    names = (
        [f"python{selector}"] if selector else
        ["python3.12", "python3.11", "python3.13", "python3", "python"]
    )
    candidates.extend(found for name in names if (found := shutil.which(name)))
    if version and os.name == "nt" and (launcher := shutil.which("py")):
        result = run(
            [launcher, f"-{selector}", "-I", "-c", "import sys; print(sys.executable)"],
            root, env, capture=True,
        )
        if result.returncode == 0:
            candidates.append(result.stdout.strip())
    for candidate in dict.fromkeys(candidates):
        try:
            info = probe(candidate, root, env)
        except SetupError:
            continue
        if version is None or tuple(info["version"][:2]) == version:
            return candidate
    if uv:
        request = selector or RECOMMENDED_PYTHON
        find = [uv, "python", "find", "--no-project", "--system", request]
        result = run(find, root, env, capture=True)
        if result.returncode:
            checked(
                [uv, "python", "install", "--no-bin", "--no-registry", request],
                root, env,
            )
            result = run(find, root, env, capture=True)
        if result.returncode:
            raise SetupError(f"uv could not locate Python {request}.", result.returncode)
        python = result.stdout.strip()
        info = probe(python, root, env)
        if tuple(info["version"][:2]) != tuple(map(int, request.split("."))):
            raise SetupError(f"uv returned a different Python than requested ({request}).")
        return python
    raise SetupError(
        f"No compatible Python {selector or '3.11-3.13'} found. "
        "Install Python 3.12 and pass its path with --python, or install uv using "
        "your OS package manager and rerun with --installer uv."
    )


def native_guidance() -> str:
    if sys.platform == "win32":
        native = (
            "Windows: Python 3.12 is available with `winget install Python.Python.3.12`. "
            "Prefer wheels; source builds may need Visual Studio C++ Build Tools and "
            "Cairo/Pango development libraries."
        )
    elif sys.platform == "darwin":
        native = "macOS (Homebrew): `brew install python@3.12 cairo pango pkg-config`."
    else:
        native = (
            "Debian/Ubuntu: `sudo apt install python3-venv python3-dev build-essential "
            "pkg-config libcairo2-dev libpango1.0-dev`. Fedora: `sudo dnf install "
            "python3-devel gcc pkgconf-pkg-config cairo-devel pango-devel`. "
            "Use a Python 3.11-3.13 interpreter and matching -venv/-dev packages."
        )
    return (
        f"Manual prerequisites (nothing is installed automatically): {native}\n"
        "FFmpeg: `winget install Gyan.FFmpeg`, `brew install ffmpeg`, or "
        "`sudo apt install ffmpeg` / `sudo dnf install ffmpeg`, as appropriate. "
        "LaTeX is optional for Tex/MathTex scenes (MiKTeX, MacTeX, or TeX Live).\n"
        "Platform details: https://docs.manim.community/en/stable/installation.html"
    )


def ensure_local_pip(python: str, root: Path, env: dict[str, str]) -> None:
    result = run([python, "-I", "-c", PIP_PROBE], root, env, capture=True)
    if result.returncode or result.stdout.strip() not in ("present", "missing"):
        raise SetupError("Could not check pip in .venv; no installer was run.", result.returncode)
    if result.stdout.strip() == "missing":
        checked([python, "-I", "-m", "ensurepip", "--upgrade"], root, env)


def setup(args: argparse.Namespace, root: Path) -> None:
    root = root.resolve()
    venv = root / ".venv"
    env = child_environment(venv)
    uv = shutil.which("uv") if args.installer != "pip" else None
    if args.installer == "uv" and not uv:
        raise SetupError(
            "uv is not installed. Install it with your OS package manager, "
            "or rerun with --installer pip and a supported Python."
        )
    installer = "uv" if uv else "pip"
    if uv and not (root / "uv.lock").is_file():
        raise SetupError("uv.lock is missing. Use a complete checkout; setup will not generate a lock.")
    doctor = root / "scripts" / "doctor.py"
    if not doctor.is_file():
        raise SetupError("scripts/doctor.py is missing. Use a complete checkout before installing.")
    version = selector_version(args.python)
    existing = existing_python(venv, root, env)
    if existing:
        python, info = existing
        if args.python:
            requested = version
            if requested is None:
                requested = tuple(probe(executable(args.python), root, env)["version"][:2])
            if tuple(info["version"][:2]) != requested:
                raise SetupError(
                    f"Existing .venv uses Python {'.'.join(map(str, info['version'][:2]))}, "
                    f"which conflicts with --python {args.python}. It was left unchanged. "
                    "Omit --python to reuse it, or move .venv aside manually first."
                )
    else:
        python = choose_python(args.python, uv, root, env)
    extras = (["dev"] if args.dev else [])
    if extra := PROVIDER_EXTRAS[args.provider]:
        extras.append(extra)
    print(f"Installing with {installer} into {venv} (extras: {', '.join(extras) or 'none'}).", flush=True)
    if uv:
        command = [
            uv, "sync", "--project", str(root), "--locked",
            "--no-default-groups", "--inexact", "--no-python-downloads", "--python", python,
        ]
        for extra in extras:
            command.extend(["--extra", extra])
        checked(command, root, env)
    else:
        if not existing:
            checked([python, "-I", "-m", "venv", str(venv)], root, env)
        local = existing_python(venv, root, env)
        if local is None:
            raise SetupError("venv creation did not produce a local environment; pip was not run.")
        ensure_local_pip(local[0], root, env)
        requirement = str(root) + (f"[{','.join(extras)}]" if extras else "")
        checked(
            [str(venv_python(venv)), "-I", "-m", "pip", "install",
             "--disable-pip-version-check", "--editable", requirement],
            root, env,
        )
    installed = existing_python(venv, root, env)
    if installed is None:
        raise SetupError("Installer finished without creating .venv; doctor was not run.")
    checked(
        [installed[0], str(doctor), "--provider", args.provider, "--skip-credentials"],
        root, env,
    )
    print("Setup complete. No activation needed; use scripts/render.ps1 or scripts/render.sh.")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        setup(args, ROOT)
    except (SetupError, OSError) as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        print(native_guidance(), file=sys.stderr)
        return exc.returncode if isinstance(exc, SetupError) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
