param(
    [switch]$CnmOnly,
    [switch]$ConsoleOnly,
    [switch]$ForceDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot

# Load .env so port display reflects any local overrides
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | Where-Object { $_ -match "^\s*[^#]" -and $_ -match "=" } | ForEach-Object {
        $parts = $_ -split "=", 2
        [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
    }
}

$CnmApiPort      = if ($env:CNM_API_PORT)      { $env:CNM_API_PORT }      else { "5011" }
$CnmFrontendPort = if ($env:CNM_FRONTEND_PORT) { $env:CNM_FRONTEND_PORT } else { "5010" }
$ConsolePort     = if ($env:PORT)              { $env:PORT }              else { "5012" }

Write-Host ""
Write-Host "  Doane Ethos Console — Local Hub"
Write-Host "  ================================"
Write-Host "  CNM (Change Notification Manager) → http://localhost:$CnmFrontendPort (frontend)"
Write-Host "                                       http://localhost:$CnmApiPort (API)"
Write-Host "  Ethos Dev Console                 → http://localhost:$ConsolePort"
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
