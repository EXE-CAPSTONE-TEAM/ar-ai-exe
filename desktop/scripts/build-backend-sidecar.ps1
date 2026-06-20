param(
    [string]$Configuration = "desktop"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktopDir = Resolve-Path (Join-Path $scriptDir "..")
$repoRoot = Resolve-Path (Join-Path $desktopDir "..")
$backendDir = Join-Path $repoRoot "backend"
$python = Join-Path $backendDir ".venv\Scripts\python.exe"
$entrypoint = Join-Path $backendDir "app\desktop_entrypoint.py"
$sidecarDir = Join-Path $desktopDir "sidecars"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend virtual environment was not found: $python"
}

if (-not (Test-Path -LiteralPath $entrypoint)) {
    throw "Desktop backend entrypoint was not found: $entrypoint"
}

& $python -m PyInstaller --version | Out-Null

New-Item -ItemType Directory -Force -Path $sidecarDir | Out-Null

Push-Location $backendDir
try {
    & $python -m PyInstaller `
        --clean `
        --onefile `
        --name kusshoes-backend `
        --paths $backendDir `
        --distpath $sidecarDir `
        --workpath (Join-Path $backendDir "build\desktop-sidecar") `
        --specpath (Join-Path $backendDir "build\desktop-sidecar") `
        $entrypoint
}
finally {
    Pop-Location
}

$exe = Join-Path $sidecarDir "kusshoes-backend.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "Sidecar build completed, but kusshoes-backend.exe was not created."
}

Write-Host "Backend sidecar ready: $exe"
