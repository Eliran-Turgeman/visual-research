param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$SceneFile,
    [Parameter(Mandatory = $true, Position = 1)]
    [string]$SceneName
)

$quality = if ($env:MANIM_QUALITY) { $env:MANIM_QUALITY } else { "-qh" }
python -m manim $quality $SceneFile $SceneName
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
