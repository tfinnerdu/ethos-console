param(
    [switch]$CnmOnly,
    [switch]$ConsoleOnly,
    [switch]$ForceDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot

Write-Host ""
Write-Host "  Doane Ethos Console — Local Hub"
Write-Host "  ================================"
Write-Host "  CNM (Change Notification Manager) → http://localhost:9500 (frontend)"
Write-Host "                                       http://localhost:9501 (API)"
Write-Host "  Ethos Dev Console                 → http://localhost:9502"
Write-Host ""

$forceSwitches = if ($ForceDeps) { "-ForceDeps" } else { "" }

if (-not $ConsoleOnly) {
    Write-Host "[Hub] Starting CNM..."
    $cnmScript = Join-Path $Root "cnm\start-local.ps1"
    Start-Process powershell `
        -ArgumentList "-NoExit -File `"$cnmScript`" -ApiOnly $forceSwitches" `
        -WindowStyle Normal
}

if (-not $CnmOnly) {
    Write-Host "[Hub] Starting Ethos Dev Console..."
    $consoleScript = Join-Path $Root "console\start-local.ps1"
    Start-Process powershell `
        -ArgumentList "-NoExit -File `"$consoleScript`" $forceSwitches" `
        -WindowStyle Normal
}

if (-not $ConsoleOnly) {
    Write-Host "[Hub] Starting CNM frontend..."
    $frontendDir = Join-Path $Root "cnm\frontend"
    Push-Location $frontendDir
    if ($ForceDeps) { npm install }
    npm run dev
    Pop-Location
}
