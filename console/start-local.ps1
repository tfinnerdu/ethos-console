param(
    [switch]$ForceDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$RepoRoot = Split-Path $Root -Parent
$LogDir = Join-Path $Root ".logs"
$AppLog = Join-Path $LogDir "app.log"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory $LogDir | Out-Null }

function Set-EnvFromFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $false }
    Get-Content $Path | Where-Object { $_ -match "^\s*[^#]" -and $_ -match "=" } | ForEach-Object {
        $parts = $_ -split "=", 2
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        # Strip surrounding quotes — both " and ' — so a value written as
        # DEFAULT_ENV="Prod" gets stored as Prod, not "Prod" (which would never
        # match a configured env name in Python).
        if ($value.Length -ge 2) {
            $first = $value[0]; $last = $value[$value.Length - 1]
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
    return $true
}

# Load repo-root .env, then console-local .env (local overrides root)
$rootLoaded = Set-EnvFromFile (Join-Path $RepoRoot ".env")
$consoleLoaded = Set-EnvFromFile (Join-Path $Root ".env")
if ($rootLoaded)    { Write-Host "[EthosConsole] Loaded $(Join-Path $RepoRoot '.env')" }
if ($consoleLoaded) { Write-Host "[EthosConsole] Loaded $(Join-Path $Root '.env')" }
if (-not $rootLoaded -and -not $consoleLoaded) {
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

Write-Host "[EthosConsole] Starting Ethos Dev Console on http://localhost:$Port"
Write-Host "[EthosConsole] Log file: $AppLog"
Write-Host "[EthosConsole] Press Ctrl+C to stop."

# Run python directly. Output streams to the parent shell (so the hub launcher
# captures it through its normal pipe) and is tee'd to a log file for
# after-the-fact debugging. No new window is spawned.
Push-Location $Root
try {
    & $PythonPath run.py 2>&1 | Tee-Object -FilePath $AppLog
} finally {
    Pop-Location
}
