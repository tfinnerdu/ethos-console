param(
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

$ConsolePort = if ($env:PORT) { $env:PORT } else { "5012" }

Write-Host ""
Write-Host "  Doane Ethos Console"
Write-Host "  ==================="
Write-Host "  http://localhost:$ConsolePort"
Write-Host ""

$forceSwitches = if ($ForceDeps) { "-ForceDeps" } else { "" }

$consoleScript = Join-Path $Root "console\start-local.ps1"
Start-Process powershell `
    -ArgumentList "-NoExit -File `"$consoleScript`" $forceSwitches" `
    -WindowStyle Normal

Write-Host "[Hub] Console launched in a separate window."
