"""Offline installation diagnostics, sharing managed render prerequisite checks.

Use ``python scripts/doctor.py`` even before installing Manim. The default
provider is explicitly silent, independent of environment settings or API keys.
Only selected provider configuration, imports and credentials are checked.
``--skip-credentials`` checks installation, NOT account readiness. No speech
service is constructed and no network request or package installation is made.

``--scene`` reads source without executing it, using production's direct-TeX
detection. Indirect TeX use needs ``--require-tex``. TeX is otherwise optional.
Native module imports run in bounded child processes so DLL failures, crashes
and noisy imports cannot corrupt the report or print credentials.

JSON schema version 1 contains ``ok``, ``provider``, ``credential_policy`` and
an ordered ``checks`` list. Each check has a stable ``id``, ``status`` (pass,
error, skipped), ``message`` and ``remediation`` list. Installed module versions
are informational, not a second dependency lock. Exit 0 means no check failed;
explicit skips do not certify skipped prerequisites. Usage errors exit 2,
diagnostic failures exit 1. Reports omit exception text, tool output, settings
values, environment dumps, timestamps and local paths.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import re
import sys


# Loading by file avoids manim_lib's eager Manim-dependent public exports.
_spec = importlib.util.spec_from_file_location(
    "_visual_research_production", Path(__file__).with_name("production.py")
)
production = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(production)

_DISTRIBUTIONS = {
    "manim": "manim",
    "av": "av",
    "manim_voiceover": "manim-voiceover",
    "openai": "openai",
    "azure.cognitiveservices.speech": "azure-cognitiveservices-speech",
    "gtts": "gTTS",
    "mutagen": "mutagen",
}


def installation_guidance(kind: str, system: str) -> list[str]:
    """Commands are suggestions only; Linux native packages target Debian/Ubuntu."""
    commands = {
        "Windows": {
            "python": ["winget install --exact --id Python.Python.3.12"],
            "native": ["winget install --exact --id Microsoft.VCRedist.2015+.x64",
                       "Use 64-bit Python and reinstall the project to restore Manim/PyAV native wheels."],
            "ffmpeg": ["winget install --exact --id Gyan.FFmpeg"],
            "tex": ["winget install --exact --id MiKTeX.MiKTeX",
                    "In MiKTeX Console install missing packages and ensure latex and dvisvgm are on PATH."],
        },
        "Darwin": {
            "python": ["brew install python@3.12"],
            "native": ["brew install cairo pango pkg-config"],
            "ffmpeg": ["brew install ffmpeg"],
            "tex": ["brew install --cask mactex-no-gui",
                    "Add /Library/TeX/texbin to PATH and reopen your shell."],
        },
        "Linux": {
            "python": ["uv python install 3.12"],
            "native": [
                "Debian/Ubuntu: sudo apt-get update && sudo apt-get install -y "
                "build-essential python3-dev pkg-config libcairo2-dev libpango1.0-dev",
            ],
            "ffmpeg": ["Debian/Ubuntu: sudo apt-get install -y ffmpeg"],
            "tex": [
                "Debian/Ubuntu: sudo apt-get install -y texlive-latex-extra "
                "texlive-fonts-extra texlive-science dvisvgm",
            ],
        },
    }
    if system not in commands:
        return [f"Install {kind} prerequisites with your system package manager, then rerun the doctor."]
    guidance = list(commands[system][kind])
    if kind == "python":
        guidance.append("Create a fresh environment with Python >=3.11,<3.14; rerun using that interpreter.")
    elif kind == "ffmpeg":
        guidance.append(
            "Reopen your shell after PATH changes, or run: python -m pip install imageio-ffmpeg"
        )
    return guidance


def _report(provider: str, skip_credentials: bool, checks: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "ok": not any(check["status"] == "error" for check in checks),
        "provider": provider,
        "credential_policy": "skip" if skip_credentials else "check",
        "checks": checks,
    }


def diagnose(
    *,
    provider: str = "none",
    scene: Path | None = None,
    require_tex: bool = False,
    skip_credentials: bool = False,
    environ: dict | None = None,
    system: str | None = None,
) -> dict:
    """Collect independent failures instead of stopping at the first prerequisite."""
    env = os.environ if environ is None else environ
    system = platform.system() if system is None else system
    checks = []

    def skipped(identifier, message):
        checks.append({"id": identifier, "status": "skipped", "message": message, "remediation": []})

    def check(identifier, action, success, failure, remediation):
        try:
            # Some fallback resolvers warn; never include their output or exceptions.
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                value = action()
        except Exception:
            checks.append({
                "id": identifier, "status": "error", "message": failure,
                "remediation": remediation,
            })
            return False, None
        checks.append({"id": identifier, "status": "pass", "message": success, "remediation": []})
        return True, value

    check(
        "python", production.check_python,
        f"Python {'.'.join(map(str, sys.version_info[:3]))} is supported (>=3.11,<3.14).",
        f"Python {'.'.join(map(str, sys.version_info[:3]))} is unsupported; use >=3.11,<3.14.",
        installation_guidance("python", system),
    )
    if provider not in production.PROVIDERS:
        checks.append({
            "id": "provider", "status": "error", "message": "Unknown provider.",
            "remediation": [f"Choose one of: {', '.join(production.PROVIDERS)}."],
        })
        return _report("invalid", skip_credentials, checks)
    check(
        "settings",
        lambda: production.resolve_settings(provider=provider, quality="-ql", environ=env),
        f"Selected provider configuration is valid: {provider}.",
        f"Selected {provider} configuration is invalid.",
        [f"Correct or unset {provider.upper()}_TTS_* settings; use the provider's supported identifiers and numeric ranges."],
    )

    needs_tex = require_tex
    if scene is None:
        skipped("scene", "No scene requested; indirect TeX use needs --require-tex.")
    else:
        def inspect_scene():
            source = Path(scene)
            production.check_scene_file(source)
            return production.scene_requires_tex(source)

        valid, direct_tex = check(
            "scene", inspect_scene, "Scene source is readable; checked direct TeX use without execution.",
            "Scene source is missing, unreadable, or not valid UTF-8 Python.",
            ["Pass --scene with an existing readable .py file, or omit --scene for installation-only checks."],
        )
        needs_tex = needs_tex or (valid and direct_tex)

    for module in production.required_modules(provider):
        passed, _ = check(
            f"module:{module}",
            lambda module=module: production.check_module(module, provider, isolated=True),
            f"{module} imports successfully.",
            f"Cannot import {module}; it is missing, incompatible, or a native dependency failed to load.",
            [f"Run in the selected environment: python -m {production.dependency_install_command(module, provider)}",
             *installation_guidance("native", system)],
        )
        if passed:
            try:
                version = importlib.metadata.version(_DISTRIBUTIONS[module])
            except (importlib.metadata.PackageNotFoundError, OSError, ValueError):
                continue
            if re.fullmatch(r"\d+(?:\.\d+){1,3}", version):
                checks[-1]["version"] = version

    check(
        "ffmpeg", production.check_ffmpeg,
        "FFmpeg runs (-version); system PATH is preferred over imageio-ffmpeg.",
        "FFmpeg is unavailable, failed to run, or returned an invalid version.",
        installation_guidance("ffmpeg", system),
    )
    for tool in ("latex", "dvisvgm"):
        if needs_tex:
            check(
                f"tool:{tool}", lambda tool=tool: production.check_tex_tool(tool),
                f"{tool} runs (--version).", f"{tool} is required but missing or failed to run.",
                installation_guidance("tex", system),
            )
        else:
            skipped(f"tool:{tool}", "TeX is optional; request --require-tex or a scene with direct TeX use.")

    credentials = production.CREDENTIALS.get(provider, ())
    if not credentials:
        skipped("credentials", f"Provider {provider} requires no credentials.")
    for name in credentials:
        if skip_credentials:
            skipped(f"credential:{name}", f"{name} was not checked (--skip-credentials); account readiness is unverified.")
        else:
            check(
                f"credential:{name}", lambda name=name: production.check_credential(name, provider, env),
                f"{name} is set; validity and account access were not tested.",
                f"{name} is required for {provider} but is not set.",
                [f"Set {name} in your current shell or trusted local secret manager; never commit it.",
                 "Use --skip-credentials for installation-only checks, or --provider none for silent rendering."],
            )
    return _report(provider, skip_credentials, checks)


class _UsageError(ValueError):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _UsageError("Invalid arguments; run python scripts/doctor.py --help.")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = _Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", choices=production.PROVIDERS, default="none",
                        help="explicit provider to check (default: none; environment never selects it)")
    parser.add_argument("--scene", type=Path, help="read a scene for direct TeX use; never execute it")
    parser.add_argument("--require-tex", action="store_true", help="require latex and dvisvgm, including indirect TeX use")
    parser.add_argument("--skip-credentials", action="store_true",
                        help="check provider installation only; do not certify account readiness")
    parser.add_argument("--json", action="store_true", help="print deterministic JSON (including argument errors)")
    try:
        args = parser.parse_args(argv)
    except _UsageError as exc:
        report = _report("invalid", False, [{
            "id": "arguments", "status": "error", "message": str(exc),
            "remediation": ["Run python scripts/doctor.py --help for supported arguments."],
        }])
        exit_code = 2
    else:
        report = diagnose(
            provider=args.provider, scene=args.scene, require_tex=args.require_tex,
            skip_credentials=args.skip_credentials,
        )
        exit_code = 0 if report["ok"] else 1
    if "--json" in argv:
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    else:
        for check in report["checks"]:
            print(f"[{check['status'].upper()}] {check['id']}: {check['message']}")
            for instruction in check["remediation"]:
                print(f"  Fix: {instruction}")
        print("Requested installation checks passed." if report["ok"] else "Installation checks failed.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
