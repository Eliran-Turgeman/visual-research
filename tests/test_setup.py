"""Bootstrap contracts; installer subprocesses never touch real environments."""

import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bootstrap_setup", ROOT / "scripts" / "setup.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def python_info(root, version=(3, 12, 4), *, virtual=True):
    return {
        "version": list(version),
        "prefix": str(root / ".venv") if virtual else str(root / "system-python"),
        "base_prefix": str(root / "system-python"),
    }


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "checkout with spaces"
    root.mkdir()
    monkeypatch.setattr(bootstrap, "ROOT", root)
    real_is_file = Path.is_file
    # Doctor and the lock belong to preceding PRs. Model their presence, not content.
    monkeypatch.setattr(
        Path, "is_file",
        lambda path: path in (root / "uv.lock", root / "scripts" / "doctor.py")
        or real_is_file(path),
    )
    return root


def make_venv(root, *, system_site=False):
    venv = root / ".venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text(
        f"include-system-site-packages = {str(system_site).lower()}\n", encoding="utf-8",
    )
    return venv


@pytest.fixture
def installer(project, monkeypatch):
    calls = []
    state = {"uv": True, "failure": None, "code": 19, "version": (3, 12, 4), "pip": True}

    def which(name):
        if name == "uv" and state["uv"]:
            return "installed-uv"
        return None

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[-1] == bootstrap.PYTHON_PROBE:
            virtual = command[0] == str(bootstrap.venv_python(project / ".venv"))
            info = python_info(project, state["version"], virtual=virtual)
            return subprocess.CompletedProcess(command, 0, json.dumps(info), "")
        if command[-1] == bootstrap.PIP_PROBE:
            return subprocess.CompletedProcess(command, 0, "present" if state["pip"] else "missing", "")
        step = (
            "doctor" if str(project / "scripts" / "doctor.py") in command else
            "ensurepip" if "ensurepip" in command else
            "install" if "sync" in command or "install" in command else "venv"
        )
        if step == state["failure"]:
            return subprocess.CompletedProcess(command, state["code"], "", "")
        if ("sync" in command or "venv" in command) and not (project / ".venv").exists():
            make_venv(project)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(bootstrap.shutil, "which", which)
    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    return state, calls


def commands(calls):
    return [command for command, _ in calls]


@pytest.mark.parametrize("provider,extra", bootstrap.PROVIDER_EXTRAS.items())
@pytest.mark.parametrize("dev", [False, True])
@pytest.mark.parametrize("backend", ["uv", "pip"])
def test_optional_extras_and_doctor_contract(project, installer, provider, extra, dev, backend):
    state, calls = installer
    args = ["--installer", backend, "--provider", provider] + (["--dev"] if dev else [])
    assert bootstrap.main(args) == 0
    executed = commands(calls)
    assert executed[-1] == [
        str(bootstrap.venv_python(project / ".venv")),
        str(project / "scripts" / "doctor.py"), "--provider", provider, "--skip-credentials",
    ]
    expected_extras = (["dev"] if dev else []) + ([extra] if extra else [])
    if backend == "uv":
        sync = next(cmd for cmd in executed if "sync" in cmd)
        assert "--locked" in sync and "--no-default-groups" in sync and "--inexact" in sync
        assert sync[sync.index("--project") + 1] == str(project)
        assert [sync[i + 1] for i, arg in enumerate(sync) if arg == "--extra"] == expected_extras
        assert not any("pip" in cmd or "venv" in cmd for cmd in executed)
    else:
        install = next(cmd for cmd in executed if "install" in cmd)
        suffix = f"[{','.join(expected_extras)}]" if expected_extras else ""
        assert install[-1] == str(project) + suffix
        assert install[:4] == [str(bootstrap.venv_python(project / ".venv")), "-I", "-m", "pip"]
        assert "--editable" in install
        assert not any("installed-uv" in cmd for cmd in executed)
    assert all(kwargs["cwd"] == project for _, kwargs in calls)
    assert all(kwargs["env"]["UV_PROJECT_ENVIRONMENT"] == str(project / ".venv") for _, kwargs in calls)


@pytest.mark.parametrize("available,expected", [(True, "sync"), (False, "install")])
def test_auto_only_falls_back_when_uv_unavailable(project, installer, available, expected):
    state, calls = installer
    state["uv"] = available
    assert bootstrap.main([]) == 0
    assert any(expected in command for command in commands(calls))


@pytest.mark.parametrize("backend,step", [("uv", "install"), ("pip", "venv"), ("pip", "install")])
def test_install_failures_forward_exit_without_doctor_or_fallback(project, installer, capsys, backend, step):
    state, calls = installer
    state["failure"] = step
    assert bootstrap.main(["--installer", backend]) == 19
    assert not any(str(project / "scripts" / "doctor.py") in cmd for cmd in commands(calls))
    if backend == "uv":
        assert not any("pip" in cmd for cmd in commands(calls))
    output = capsys.readouterr()
    assert "Setup complete" not in output.out
    assert "Manual prerequisites" in output.err


@pytest.mark.parametrize("backend", ["uv", "pip"])
def test_doctor_failure_is_not_success(project, installer, capsys, backend):
    state, _ = installer
    state["failure"] = "doctor"
    state["code"] = 7
    assert bootstrap.main(["--installer", backend]) == 7
    assert "Setup complete" not in capsys.readouterr().out


@pytest.mark.parametrize("backend", ["uv", "pip"])
def test_reuse_existing_environment_without_recreation(project, installer, backend):
    _, calls = installer
    make_venv(project)
    marker = project / ".venv" / "keep-me"
    marker.write_text("user data", encoding="utf-8")
    assert bootstrap.main(["--installer", backend]) == 0
    assert marker.read_text(encoding="utf-8") == "user data"
    assert not any("venv" in cmd for cmd in commands(calls))
    if backend == "uv":
        sync = next(cmd for cmd in commands(calls) if "sync" in cmd)
        assert sync[sync.index("--python") + 1] == str(bootstrap.venv_python(project / ".venv"))


@pytest.mark.parametrize("bad_version", [(3, 10, 9), (3, 14, 0)])
def test_incompatible_existing_environment_left_unchanged(project, installer, capsys, bad_version):
    state, calls = installer
    state["version"] = bad_version
    make_venv(project)
    assert bootstrap.main([]) == 1
    assert len(calls) == 1
    assert "Move it aside manually" in capsys.readouterr().err


@pytest.mark.parametrize("kind", ["missing-config", "system-site", "wrong-prefix", "broken-python"])
def test_invalid_existing_environment_never_installs(project, installer, monkeypatch, kind):
    _, calls = installer
    make_venv(project, system_site=(kind == "system-site"))
    if kind == "missing-config":
        (project / ".venv" / "pyvenv.cfg").unlink()
    elif kind == "wrong-prefix":
        monkeypatch.setattr(bootstrap, "probe", lambda *args: python_info(project, virtual=False))
    elif kind == "broken-python":
        monkeypatch.setattr(bootstrap.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("broken Python")))
    assert bootstrap.main([]) == 1
    assert not any("sync" in cmd or "install" in cmd for cmd in commands(calls))


def test_existing_environment_selector_conflict(project, installer, capsys):
    _, calls = installer
    make_venv(project)
    assert bootstrap.main(["--python", "3.13"]) == 1
    assert len(calls) == 1
    assert "conflicts with --python 3.13" in capsys.readouterr().err


def test_switching_uv_to_pip_seeds_only_existing_local_environment(project, installer):
    state, calls = installer
    state["pip"] = False
    assert bootstrap.main(["--installer", "uv"]) == 0
    marker = project / ".venv" / "keep-me"
    marker.write_text("user data", encoding="utf-8")
    calls.clear()
    assert bootstrap.main(["--installer", "pip"]) == 0
    executed = commands(calls)
    seed = [str(bootstrap.venv_python(project / ".venv")), "-I", "-m", "ensurepip", "--upgrade"]
    assert seed in executed
    assert not any("venv" in cmd or "installed-uv" in cmd for cmd in executed)
    assert marker.read_text(encoding="utf-8") == "user data"
    assert executed.index(seed) < next(i for i, cmd in enumerate(executed) if "install" in cmd)


def test_existing_pip_is_not_reseeded_or_upgraded(project, installer):
    _, calls = installer
    make_venv(project)
    assert bootstrap.main(["--installer", "pip"]) == 0
    assert not any("ensurepip" in cmd for cmd in commands(calls))


def test_missing_ensurepip_fails_without_install_or_doctor(project, installer, capsys):
    state, calls = installer
    state.update(pip=False, failure="ensurepip", code=29)
    make_venv(project)
    assert bootstrap.main(["--installer", "pip"]) == 29
    executed = commands(calls)
    assert not any("install" in cmd or str(project / "scripts" / "doctor.py") in cmd for cmd in executed)
    assert "Manual prerequisites" in capsys.readouterr().err


@pytest.mark.parametrize("stdout,returncode", [("", 17), ("invalid", 0)])
def test_failed_pip_probe_does_not_seed_or_install(project, monkeypatch, stdout, returncode):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, returncode, stdout, "")

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    with pytest.raises(bootstrap.SetupError, match="Could not check pip") as result:
        bootstrap.ensure_local_pip(str(bootstrap.venv_python(project / ".venv")), project, {})
    assert result.value.returncode == (returncode or 1)
    assert len(calls) == 1


def test_matching_selector_reuses_venv_without_download(project, installer):
    _, calls = installer
    make_venv(project)
    assert bootstrap.main(["--python", "3.12"]) == 0
    assert not any("find" in cmd or "venv" in cmd for cmd in commands(calls))


@pytest.mark.parametrize("selector", ["3.10", "3.14", "2", "3.12.1", "nonexistent-python"])
def test_invalid_selector_does_not_install(project, installer, selector):
    _, calls = installer
    assert bootstrap.main(["--python", selector]) == 1
    assert not any("sync" in cmd or "install" in cmd for cmd in commands(calls))


def test_explicit_unavailable_uv_does_not_use_pip(project, installer):
    state, calls = installer
    state["uv"] = False
    assert bootstrap.main(["--installer", "uv"]) == 1
    assert not calls


@pytest.mark.parametrize("missing", ["uv.lock", "scripts/doctor.py"])
def test_incomplete_checkout_fails_before_install(project, installer, monkeypatch, missing):
    _, calls = installer
    real_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda path: path != project / missing and real_is_file(path))
    assert bootstrap.main([]) == 1
    assert not calls


def test_help_does_not_probe_or_install(monkeypatch, capsys):
    monkeypatch.setattr(bootstrap, "setup", lambda *args: pytest.fail("must not install"))
    with pytest.raises(SystemExit) as result:
        bootstrap.main(["--help"])
    assert result.value.code == 0
    output = capsys.readouterr().out
    assert "--installer" in output and "--provider" in output and "--python" in output


def test_caller_environment_cannot_redirect_installs(project, monkeypatch):
    for key in (
        "VIRTUAL_ENV", "CONDA_PREFIX", "PYTHONPATH", "PYTHONHOME",
        "PIP_TARGET", "PIP_PREFIX", "PIP_USER", "PIP_PYTHON", "UV_PROJECT",
        "UV_PYTHON", "UV_WORKING_DIRECTORY", "UV_PROJECT_ENVIRONMENT",
    ):
        monkeypatch.setenv(key, "unrelated-environment")
    env = bootstrap.child_environment(project / ".venv")
    assert env["UV_PROJECT_ENVIRONMENT"] == str(project / ".venv")
    assert env["PIP_CONFIG_FILE"] == os.devnull
    assert env["PIP_REQUIRE_VIRTUALENV"] == "true"
    assert "unrelated-environment" not in env.values()
    assert os.environ["VIRTUAL_ENV"] == "unrelated-environment"


@pytest.mark.parametrize("available,install_code", [(True, 0), (False, 0), (False, 23)])
def test_uv_interpreter_acquisition_is_managed_only(project, monkeypatch, available, install_code):
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: None)
    calls = []
    find_count = 0
    managed = str(project / "managed Python" / "python.exe")

    def fake_run(command, **kwargs):
        nonlocal find_count
        calls.append(command)
        if "find" in command:
            find_count += 1
            found = available or find_count > 1
            return subprocess.CompletedProcess(command, 0 if found else 1, managed if found else "", "")
        if "install" in command:
            return subprocess.CompletedProcess(command, install_code, "", "")
        info = python_info(project, (3, 12, 4) if command[0] == managed else (3, 14, 0), virtual=False)
        return subprocess.CompletedProcess(command, 0, json.dumps(info), "")

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    env = bootstrap.child_environment(project / ".venv")
    if install_code:
        with pytest.raises(bootstrap.SetupError) as result:
            bootstrap.choose_python(None, "uv", project, env)
        assert result.value.returncode == install_code
    else:
        assert bootstrap.choose_python(None, "uv", project, env) == managed
    installs = [cmd for cmd in calls if "install" in cmd]
    assert installs == ([] if available else [["uv", "python", "install", "--no-bin", "--no-registry", "3.12"]])


def test_pip_missing_compatible_python_is_actionable(project, monkeypatch):
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        bootstrap, "probe",
        lambda *args: (_ for _ in ()).throw(bootstrap.SetupError("unsupported")),
    )
    with pytest.raises(bootstrap.SetupError, match="Install Python 3.12"):
        bootstrap.choose_python(None, None, project, {})


def test_relative_interpreter_with_spaces_is_resolved_before_project_cwd(project, monkeypatch):
    caller = project.parent / "caller with spaces"
    caller.mkdir()
    python = caller / "custom python.exe"
    python.touch()
    monkeypatch.chdir(caller)
    monkeypatch.setattr(bootstrap, "probe", lambda *args: python_info(project, virtual=False))
    assert bootstrap.choose_python("custom python.exe", None, project, {}) == str(python.resolve())


def test_redirected_venv_is_rejected_before_running_python(project, installer, monkeypatch):
    _, calls = installer
    make_venv(project)
    real_resolve = Path.resolve
    monkeypatch.setattr(
        Path, "resolve",
        lambda path, **kwargs: project.parent / "shared-venv"
        if path == project / ".venv" else real_resolve(path, **kwargs),
    )
    assert bootstrap.main([]) == 1
    assert calls == []


@pytest.mark.skipif(os.name != "nt", reason="Windows Python launcher")
def test_pip_explicit_version_uses_windows_launcher(project, monkeypatch):
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: "py" if name == "py" else None)
    selected = str(project / "Python313" / "python.exe")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[0] == "py":
            return subprocess.CompletedProcess(command, 0, selected + "\n", "")
        version = (3, 13, 2) if command[0] == selected else (3, 12, 4)
        return subprocess.CompletedProcess(command, 0, json.dumps(python_info(project, version, virtual=False)), "")

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    assert bootstrap.choose_python("3.13", None, project, {}) == selected
    assert calls[0] == ["py", "-3.13", "-I", "-c", "import sys; print(sys.executable)"]


def shell_executable(shell):
    if shell == "powershell":
        executable = shutil.which("pwsh") or shutil.which("powershell")
    elif shell == "windows-powershell":
        executable = shutil.which("powershell")
    else:
        executable = (
            str(Path(os.environ.get("ProgramFiles", "")) / "Git" / "bin" / "bash.exe")
            if os.name == "nt" else shutil.which("bash")
        )
    if not executable or not Path(executable).is_file():
        pytest.skip(f"{shell} not installed")
    return executable


@pytest.mark.parametrize("shell", ["powershell", "bash"])
@pytest.mark.parametrize("argument,code", [("--help", 0), ("--not-a-setup-option", 2)])
def test_native_wrappers_from_another_cwd(tmp_path, shell, argument, code):
    executable = shell_executable(shell)
    if shell == "powershell":
        command = [executable, "-NoProfile", "-File", str(ROOT / "scripts" / "setup.ps1"), argument]
    else:
        command = [executable, str(ROOT / "scripts" / "setup.sh"), argument]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == code, result.stdout + result.stderr
    assert "--installer" in result.stdout + result.stderr


@pytest.mark.parametrize("shell", ["powershell", "windows-powershell", "bash"])
@pytest.mark.parametrize("install_code", [0, 27])
def test_wrappers_bootstrap_with_only_uv(tmp_path, shell, install_code):
    executable = shell_executable(shell)
    if shell != "bash":
        python = sys.executable.replace("'", "''")
        script = str(ROOT / "scripts" / "setup.ps1").replace("'", "''")
        source = f"""
function Get-Command {{
    param($Name, $ErrorAction)
    if ($Name -eq 'uv') {{ return 'uv' }}
}}
function uv {{
    if ($args[1] -eq 'install') {{
        if (($args -join ' ') -ne 'python install --no-bin --no-registry 3.12') {{ exit 90 }}
        $global:LASTEXITCODE = {install_code}
    }} else {{
        Write-Output '{python}'
        $global:LASTEXITCODE = 0
    }}
}}
& '{script}' --help
exit $LASTEXITCODE
"""
        command = [executable, "-NoProfile", "-Command", source]
    else:
        python = shlex.quote(sys.executable)
        script = shlex.quote(str(ROOT / "scripts" / "setup.sh"))
        source = f"""
command() {{ [[ "$2" == uv ]]; }}
uv() {{
  if [[ "$2" == install ]]; then
    [[ "$*" == "python install --no-bin --no-registry 3.12" ]] || return 90
    return {install_code}
  fi
  printf '%s\\n' {python}
}}
export -f command uv
exec {shlex.quote(executable)} {script} --help
"""
        command = [executable, "-c", source]
    result = subprocess.run(command, cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == install_code, result.stdout + result.stderr
    if install_code == 0:
        assert "--installer" in result.stdout
    else:
        assert "--installer" not in result.stdout


@pytest.mark.parametrize("shell", ["powershell", "windows-powershell", "bash"])
def test_wrappers_without_runtime_fail_with_prerequisites(tmp_path, shell):
    executable = shell_executable(shell)
    if shell != "bash":
        script = str(ROOT / "scripts" / "setup.ps1").replace("'", "''")
        source = f"""
function Get-Command {{ param($Name, $ErrorAction); return }}
& '{script}' --help
exit $LASTEXITCODE
"""
        command = [executable, "-NoProfile", "-Command", source]
    else:
        source = (
            "command() { return 1; }; export -f command; exec "
            f"{shlex.quote(executable)} {shlex.quote(str(ROOT / 'scripts' / 'setup.sh'))} --help"
        )
        command = [executable, "-c", source]
    result = subprocess.run(command, cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Python 3.11-3.13 or uv is required" in result.stderr


@pytest.mark.parametrize("shell", ["powershell", "windows-powershell", "bash"])
def test_wrappers_forward_spaces_and_python_failure(tmp_path, shell):
    executable = shell_executable(shell)
    selected = str(tmp_path / "Python with spaces" / "python.exe")
    forwarded = ["--installer", "pip", "--provider", "external-gtts", "--dev", "--python", selected]
    if shell != "bash":
        script = str(ROOT / "scripts" / "setup.ps1").replace("'", "''")
        arguments = " ".join("'" + arg.replace("'", "''") + "'" for arg in forwarded)
        source = f"""
function Get-Command {{
    param($Name, $ErrorAction)
    if ($Name -eq 'python3.12') {{ return 'python3.12' }}
}}
function python3.12 {{
    if ($args[0] -eq '-I') {{ $global:LASTEXITCODE = 0; return }}
    $args | ForEach-Object {{ Write-Output "<$_>" }}
    $global:LASTEXITCODE = 31
}}
$PSNativeCommandUseErrorActionPreference = $true
& '{script}' {arguments}
exit $LASTEXITCODE
"""
        command = [executable, "-NoProfile", "-Command", source]
        env = None
    else:
        bin_dir = tmp_path / "mock Python bin"
        bin_dir.mkdir()
        python = bin_dir / "python3.12"
        python.write_text(
            "#!/bin/bash\n"
            'if [[ "$1" == -I ]]; then exit 0; fi\n'
            'printf "<%s>\\n" "$@"\nexit 31\n',
            encoding="utf-8",
        )
        python.chmod(0o755)
        env = os.environ.copy()
        env["BOOTSTRAP_TEST_BIN"] = str(bin_dir)
        source = (
            'export PATH="$BOOTSTRAP_TEST_BIN:$PATH"; exec '
            f"{shlex.quote(executable)} {shlex.quote(str(ROOT / 'scripts' / 'setup.sh'))} "
            + " ".join(shlex.quote(arg) for arg in forwarded)
        )
        command = [executable, "-c", source]
    result = subprocess.run(command, cwd=tmp_path, env=env, text=True, capture_output=True, check=False)
    assert result.returncode == 31, result.stdout + result.stderr
    assert result.stdout.splitlines()[1:] == [f"<{arg}>" for arg in forwarded]


@pytest.mark.parametrize("shell", ["powershell", "windows-powershell", "bash"])
@pytest.mark.parametrize("equals", [False, True])
def test_wrappers_bootstrap_from_explicit_python_outside_path(tmp_path, shell, equals):
    executable = shell_executable(shell)
    argument = (
        ["--python=" + sys.executable, "--help"] if equals
        else ["--python", sys.executable, "--help"]
    )
    if shell != "bash":
        python = sys.executable.replace("'", "''")
        script = str(ROOT / "scripts" / "setup.ps1").replace("'", "''")
        arguments = " ".join("'" + arg.replace("'", "''") + "'" for arg in argument)
        source = f"""
function Get-Command {{
    param($Name, $ErrorAction)
    if ($Name -eq '{python}') {{ return $Name }}
}}
& '{script}' {arguments}
exit $LASTEXITCODE
"""
        command = [executable, "-NoProfile", "-Command", source]
    else:
        source = (
            f'command() {{ [[ "$2" == {shlex.quote(sys.executable)} ]]; }}; '
            "export -f command; exec "
            f"{shlex.quote(executable)} {shlex.quote(str(ROOT / 'scripts' / 'setup.sh'))} "
            + " ".join(shlex.quote(arg) for arg in argument)
        )
        command = [executable, "-c", source]
    result = subprocess.run(command, cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--installer" in result.stdout
