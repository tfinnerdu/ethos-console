param(
    [switch]$ForceDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$LogDir = Join-Path $Root ".logs"
$AppLog = Join-Path $LogDir "app.log"
$AppLogErr = Join-Path $LogDir "app.err"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory $LogDir | Out-Null }

# Kill any previous instance on port 9502
$portConn = Get-NetTCPConnection -LocalPort 9502 -State Listen -ErrorAction SilentlyContinue
if ($portConn) {
    Write-Host "[EthosConsole] Stopping existing process on port 9502 (PID $($portConn.OwningProcess))..."
    Stop-Process -Id $portConn.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}

# Load .env if present
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | Where-Object { $_ -match "^\s*[^#]" -and $_ -match "=" } | ForEach-Object {
        $parts = $_ -split "=", 2
        [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
    }
    Write-Host "[EthosConsole] Loaded .env"
} else {
    Write-Host "[EthosConsole] No .env found — copy .env.example to .env and fill in ETHOS_API_KEY"
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
$env:PORT = "9502"

Write-Host "[EthosConsole] Starting Ethos Dev Console on http://localhost:9502 ..."
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

Write-Host "[EthosConsole] PID $($proc.Id) — http://localhost:9502"
Wait-Process -Id $proc.Id
