param(
    [ValidateSet("-ql", "-qm", "-qh", "-qp", "-qk")]
    [string]$Quality,
    [switch]$Silent,
    [ValidateSet("draft", "production")]
    [string]$Profile = "draft",
    [ValidateSet("none", "openrouter", "gtts", "external-gtts", "openai", "azure")]
    [string]$Provider,
    [string]$OutputDir,
    [string]$RunId,
    [string]$CacheDir
)

$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$renderArgs = @("$PSScriptRoot\scene.py", "DDTreeFullExplainer", "--profile", $Profile, "--require-tex")
if ($Quality) { $renderArgs += "--quality=$Quality" }
if ($Silent) {
    if ($Provider -and $Provider -ne "none") {
        throw "-Silent cannot be combined with a non-silent -Provider."
    }
    $renderArgs += @("--provider", "none")
} elseif ($Provider) {
    $renderArgs += @("--provider", $Provider)
}
if ($OutputDir) { $renderArgs += @("--output-dir", $OutputDir) }
if ($RunId) { $renderArgs += @("--run-id", $RunId) }
if ($CacheDir) { $renderArgs += @("--cache-dir", $CacheDir) }
& "$root\scripts\render.ps1" @renderArgs
exit $LASTEXITCODE
