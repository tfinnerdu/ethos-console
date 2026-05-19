param(
    [switch]$ForceDeps,
    [switch]$ApiOnly,
    [switch]$FrontendOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$RepoRoot = Split-Path $Root -Parent
$ApiProject = Join-Path $Root "src\EthosCn.Api\EthosCn.Api.csproj"
$FrontendDir = Join-Path $Root "frontend"
$LogDir = Join-Path $RepoRoot ".hub-logs"
$ApiLog = Join-Path $LogDir "api.log"
$ApiLogErr = Join-Path $LogDir "api.err"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory $LogDir | Out-Null }

# Kill any previous API instance holding the log file open
$portConn = Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue
if ($portConn) {
    Write-Host "[CNM] Stopping existing API process on port $ApiPort (PID $($portConn.OwningProcess))..."
    Stop-Process -Id $portConn.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 750
}

# Wipe logs on each start
if (Test-Path $ApiLog) { Remove-Item $ApiLog }
if (Test-Path $ApiLogErr) { Remove-Item $ApiLogErr }

$env:ASPNETCORE_ENVIRONMENT = "Development"

# Load .env if present (key=value lines only)
$EnvFile = Join-Path $RepoRoot ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | Where-Object { $_ -match "^\s*[^#]" -and $_ -match "=" } | ForEach-Object {
        $parts = $_ -split "=", 2
        [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
    }
    Write-Host "[CNM] Loaded .env"
}

$ApiPort = if ($env:CNM_API_PORT) { $env:CNM_API_PORT } else { "5011" }

if (-not $FrontendOnly) {
    if ($ForceDeps) {
        Write-Host "[CNM] Restoring NuGet packages..."
        dotnet restore (Join-Path $RepoRoot "ethos-console.sln") | Out-Null
    }

    Write-Host "[CNM] Starting API on http://0.0.0.0:$ApiPort ..."
    $ApiProc = Start-Process `
        -FilePath "dotnet" `
        -ArgumentList "watch run --project `"$ApiProject`" --no-launch-profile --urls http://0.0.0.0:$ApiPort" `
        -NoNewWindow `
        -PassThru `
        -RedirectStandardOutput $ApiLog `
        -RedirectStandardError $ApiLogErr
    Write-Host "[CNM] API PID $($ApiProc.Id)"
}

if (-not $ApiOnly) {
    if ($ForceDeps) {
        Write-Host "[CNM] Installing frontend packages..."
        Push-Location $FrontendDir
        npm install
        Pop-Location
    }

    $FrontendPort = if ($env:CNM_FRONTEND_PORT) { $env:CNM_FRONTEND_PORT } else { "5010" }
    Write-Host "[CNM] Starting frontend on http://localhost:$FrontendPort ..."
    Push-Location $FrontendDir
    npm run dev
    Pop-Location
}

if (-not $FrontendOnly -and $ApiOnly) {
    Write-Host "[CNM] API running. Press Ctrl+C to stop."
    Wait-Process -Id $ApiProc.Id
}
