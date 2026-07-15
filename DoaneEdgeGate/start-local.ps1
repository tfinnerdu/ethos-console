# DoaneEdgeGate - local start helper
# Runs the proxy on 0.0.0.0:5058 and prints the URLs you can hit.
# ---------------------------------------------------------------------------
# One-time per machine (if scripts are blocked):
#   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
#   Unblock-File -Path .\start-local.ps1

$ErrorActionPreference = "Stop"
$port = 5058
$proj = Join-Path $PSScriptRoot "src\DoaneEdgeGate\DoaneEdgeGate.csproj"

Write-Host "---------------------------------------------------------------"
Write-Host "DoaneEdgeGate starting on port $port"
Write-Host "  http://localhost:$port/health"

# Print the first real machine IP (skip loopback, link-local, WSL, vEthernet).
$ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notlike "127.*" -and
        $_.IPAddress -notlike "169.254.*" -and
        $_.InterfaceAlias -notlike "*WSL*" -and
        $_.InterfaceAlias -notlike "*vEthernet*"
    }
foreach ($ip in $ips) {
    Write-Host ("  http://{0}:{1}/health" -f $ip.IPAddress, $port)
}
Write-Host "---------------------------------------------------------------"
Write-Host "Mode defaults to Off (passthrough). Set EdgeGate__Mode and"
Write-Host "EdgeGate__Downstream__BaseUrl before it does anything useful."
Write-Host "---------------------------------------------------------------"

$env:ASPNETCORE_URLS = "http://0.0.0.0:$port"
dotnet run --project $proj
