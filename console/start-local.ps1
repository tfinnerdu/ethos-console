param(
    [switch]$ForceDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$RepoRoot = Split-Path $Root -Parent
$LogDir = Join-Path $Root ".logs"
$AppLog = Join-Path $LogDir "app.log"
$AppLogErr = Join-Path $LogDir "app.err"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory $LogDir | Out-Null }

# Load repo-root .env, then console-local .env (local overrides root)
foreach ($envSearch in @((Join-Path $RepoRoot ".env"), (Join-Path $Root ".env"))) {
    if (Test-Path $envSearch) {
        Get-Content $envSearch | Where-Object { $_ -match "^\s*[^#]" -and $_ -match "=" } | ForEach-Object {
            $parts = $_ -split "=", 2
            [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
        }
        Write-Host "[EthosConsole] Loaded $envSearch"
    }
}
if (-not (Test-Path (Join-Path $RepoRoot ".env")) -and -not (Test-Path (Join-Path $Root ".env"))) {
    Write-Host "[EthosConsole] No .env found - copy console\.env.example to .env and fill in an ETHOS_ENV_1_* block"
}

# PORT may be set by .env; fall back to 5012
$Port = if ($env:PORT) { $env:PORT } else { "5012" }

# Kill any previous instance on the configured port
$portConn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($portConn) {
    Write-Host "[EthosConsole] Stopping existing process on port $Port (PID $($portConn.OwningProcess))..."
    Stop-Process -Id $portConn.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}

# Create/activate venv if needed
$VenvDir = Join-Path $Root ".venv"
if (-not (Test-Path $VenvDir) -or $ForceDeps) {
    Write-Host "[EthosConsole] Creating Python virtual environment..."
    python -m venv $VenvDir
}

$PipPath = Join-Path $VenvDir "Scripts\pip.exe"
$PythonPath = Join-Path $VenvDir "Scripts\python.exe"

if ($ForceDeps -or -not (Test-Path (Join-Path $VenvDir "Scripts\flask.exe"))) {
    Write-Host "[EthosConsole] Installing Python dependencies..."
    & $PipPath install -r (Join-Path $Root "requirements.txt") --quiet
}

$env:FLASK_ENV = "development"
$env:PORT = $Port

Write-Host "[EthosConsole] Starting Ethos Dev Console on http://localhost:$Port ..."
Write-Host "[EthosConsole] Logs: $AppLog"
Write-Host "[EthosConsole] Press Ctrl+C to stop."

$proc = Start-Process `
    -FilePath $PythonPath `
    -ArgumentList "run.py" `
    -WorkingDirectory $Root `
    -NoNewWindow `
    -PassThru `
    -RedirectStandardOutput $AppLog `
    -RedirectStandardError $AppLogErr

Write-Host "[EthosConsole] PID $($proc.Id) - http://localhost:$Port"
Wait-Process -Id $proc.Id
