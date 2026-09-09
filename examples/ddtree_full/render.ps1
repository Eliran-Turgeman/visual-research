param(
    [ValidateSet("-ql", "-qm", "-qh")]
    [string]$Quality = "-qh",
    [switch]$Silent
)

$root = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $root
$env:PATH = "$root\.venv\Scripts;$env:PATH"
$env:MANIM_QUALITY = $Quality
$env:MANIM_TTS_PROVIDER = if ($Silent) { "none" } else { "openrouter" }
if (-not $Silent) {
    if (-not $env:OPENROUTER_API_KEY) {
        $env:OPENROUTER_API_KEY = [Environment]::GetEnvironmentVariable(
            "OPENROUTER_API_KEY", "User"
        )
    }
    if (-not $env:OPENROUTER_API_KEY) {
        throw "OPENROUTER_API_KEY is required for MAI narration. Use -Silent only for drafts."
    }
    $env:OPENROUTER_TTS_MODEL = "microsoft/mai-voice-2"
    $env:OPENROUTER_TTS_VOICE = "en-US-Harper:MAI-Voice-2"
    $env:OPENROUTER_TTS_SPEED = "0.96"
}
& "$root\scripts\render.ps1" "$PSScriptRoot\scene.py" DDTreeFullExplainer
exit $LASTEXITCODE
