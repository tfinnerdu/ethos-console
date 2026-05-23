param(
    [switch]$ForceDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot

# Run the console's start script in-process — no extra window is spawned, so
# the hub launcher captures stdout/stderr through its normal pipe and an
# interactive `.\start-local.ps1` streams logs into your current shell.
$consoleScript = Join-Path $Root "console\start-local.ps1"
& $consoleScript @PSBoundParameters
