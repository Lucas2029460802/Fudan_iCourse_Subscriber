# Daily local entry point for Task Scheduler.
# Skips when a previous run is still going, so two processes never share the database.

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:Path = (
    [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
    [Environment]::GetEnvironmentVariable("Path", "User")
)

$logDir = Join-Path $Root "temp"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "scheduled-run.log"

function Write-Log([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $log -Value $line -Encoding utf8
}

$running = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -match "main\.py" }
if ($running) {
    $pids = ($running | ForEach-Object { $_.ProcessId }) -join ","
    Write-Log "Skip: main.py already running (PID $pids)"
    exit 0
}

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    Write-Log "Skip: python was not found on PATH"
    exit 1
}

Write-Log "Start $python"
& cmd.exe /c "`"$python`" -u main.py >> `"$log`" 2>&1"
$code = $LASTEXITCODE
Write-Log "Exit $code"
exit $code
