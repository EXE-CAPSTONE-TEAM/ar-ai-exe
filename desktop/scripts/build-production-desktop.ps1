param(
    [string]$ArtifactPath = $env:KUSSHOES_BLENDER_ARTIFACT_PATH,
    [string]$ArtifactUrl = $env:KUSSHOES_BLENDER_ARTIFACT_URL,
    [string]$Sha256 = $env:KUSSHOES_BLENDER_SHA256,
    [switch]$CleanBlender
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktopDir = Resolve-Path (Join-Path $scriptDir "..")

& (Join-Path $scriptDir "prepare-blender-runtime.ps1") `
    -ArtifactPath $ArtifactPath `
    -ArtifactUrl $ArtifactUrl `
    -Sha256 $Sha256 `
    -Clean:$CleanBlender

& (Join-Path $scriptDir "build-backend-sidecar.ps1")

Push-Location $desktopDir
try {
    npm run build
}
finally {
    Pop-Location
}
