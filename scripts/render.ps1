# All arguments are passed unchanged to the shared Python CLI, including --help.
# Set MANIM_PYTHON to an absolute interpreter path when using a separate worktree.
$ErrorActionPreference = "Stop"
$localPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$python = if ($env:MANIM_PYTHON) {
    $env:MANIM_PYTHON
} elseif (Test-Path $localPython) {
    $localPython
} else {
    "python"
}

try {
    & $python (Join-Path $PSScriptRoot "render.py") @args
    exit $LASTEXITCODE
} catch {
    Write-Error "Cannot run Python. Set MANIM_PYTHON to a Python >=3.11,<3.14 executable. $_"
    exit 1
}
