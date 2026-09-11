# Bootstrap needs only a supported Python or an already installed uv.
# --python is forwarded to setup.py; it selects the project's interpreter.
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$probe = "import sys; sys.exit(not ((3, 11) <= sys.version_info[:2] < (3, 14)))"
$script = Join-Path $PSScriptRoot "setup.py"
$requestedPython = $null
for ($i = 0; $i -lt $args.Count; $i++) {
    if ($args[$i] -eq "--python" -and $i + 1 -lt $args.Count) {
        $requestedPython = $args[$i + 1]
    } elseif ($args[$i].StartsWith("--python=")) {
        $requestedPython = $args[$i].Substring(9)
    }
}

function Invoke-Bootstrap {
    param([string]$Python, [string[]]$Prefix, [string[]]$Forwarded)
    try {
        & $Python @Prefix -I -c $probe 2>$null
        if ($LASTEXITCODE -ne 0) { return }
    } catch { return }
    & $Python @Prefix $script @Forwarded
    exit $LASTEXITCODE
}

try {
    foreach ($python in @(
        $requestedPython,
        (Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"),
        "python3.12", "python3.11", "python3.13", "python", "python3"
    )) {
        if ($python -and (Get-Command $python -ErrorAction SilentlyContinue)) {
            Invoke-Bootstrap -Python $python -Prefix @() -Forwarded $args
        }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($version in @("-3.12", "-3.11", "-3.13")) {
            Invoke-Bootstrap -Python "py" -Prefix @($version) -Forwarded $args
        }
    }
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        & uv python install --no-bin --no-registry 3.12
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $python = & uv python find --no-project --system 3.12
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $python.Trim() $script @args
        exit $LASTEXITCODE
    }
    [Console]::Error.WriteLine(
        "Python 3.11-3.13 or uv is required. Install Python with " +
        "'winget install Python.Python.3.12' or uv with 'winget install astral-sh.uv', " +
        "then rerun setup. No PATH or execution-policy changes were made."
    )
    exit 1
} catch {
    [Console]::Error.WriteLine("Cannot run setup: $_")
    exit 1
}
