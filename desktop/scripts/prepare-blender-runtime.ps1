param(
    [string]$ArtifactPath = $env:KUSSHOES_BLENDER_ARTIFACT_PATH,
    [string]$ArtifactUrl = $env:KUSSHOES_BLENDER_ARTIFACT_URL,
    [string]$Sha256 = $env:KUSSHOES_BLENDER_SHA256,
    [string]$ManifestPath = "",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktopDir = Resolve-Path (Join-Path $scriptDir "..")
$dependenciesDir = Join-Path $desktopDir "dependencies"
if (-not $ManifestPath) {
    $ManifestPath = Join-Path $dependenciesDir "blender.windows.json"
}

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "Blender manifest was not found: $ManifestPath"
}

$manifest = Get-Content -Raw -Path $ManifestPath | ConvertFrom-Json
if (-not $ArtifactUrl -and $manifest.downloadUrl) {
    $ArtifactUrl = [string]$manifest.downloadUrl
}
if (-not $Sha256 -and $manifest.sha256) {
    $Sha256 = [string]$manifest.sha256
}

if (-not $Sha256 -or $Sha256 -notmatch '^[a-fA-F0-9]{64}$') {
    throw "KUSSHOES_BLENDER_SHA256 or manifest.sha256 must be a 64-character SHA-256."
}
if ([string]$manifest.archiveType -ne "zip") {
    throw "Only zip Blender artifacts are supported."
}
if ($ArtifactUrl -and $ArtifactUrl -match 'download\.blender\.org') {
    throw "Use the internal artifact store, not direct download.blender.org runtime downloads."
}

$downloadsDir = Join-Path $dependenciesDir "downloads"
$toolsDir = Join-Path $dependenciesDir "tools"
$installRoot = Join-Path $toolsDir ([string]$manifest.name)
$archivePath = Join-Path $downloadsDir "$($manifest.name)-$($manifest.version).$($manifest.archiveType)"

New-Item -ItemType Directory -Force -Path $downloadsDir | Out-Null
New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null

if ($ArtifactPath) {
    $resolvedArtifact = Resolve-Path -LiteralPath $ArtifactPath
    Copy-Item -LiteralPath $resolvedArtifact -Destination $archivePath -Force
}
elseif ($ArtifactUrl) {
    Invoke-WebRequest -Uri $ArtifactUrl -OutFile $archivePath
}
else {
    throw "Set KUSSHOES_BLENDER_ARTIFACT_PATH or KUSSHOES_BLENDER_ARTIFACT_URL before preparing Blender."
}

$actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
if ($actualHash -ne $Sha256.ToLowerInvariant()) {
    throw "Blender artifact checksum mismatch. Expected $Sha256, got $actualHash."
}

if ($Clean -and (Test-Path -LiteralPath $installRoot)) {
    Remove-Item -LiteralPath $installRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
Expand-Archive -LiteralPath $archivePath -DestinationPath $installRoot -Force

$exePath = Join-Path $installRoot ([string]$manifest.exeRelativePath)
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Blender artifact expanded, but blender.exe was not found: $exePath"
}

$noticePath = Join-Path $dependenciesDir "BLENDER-NOTICE.txt"
if (-not (Test-Path -LiteralPath $noticePath)) {
    @"
KusShoes Desktop Blender Runtime Notice

Blender is bundled from an internal artifact and verified by SHA-256 before
release packaging. Keep the Blender license files from the artifact in the
packaged resources and comply with Blender licensing terms.
"@ | Set-Content -Path $noticePath -Encoding UTF8
}

Write-Host "Blender runtime prepared: $exePath"
