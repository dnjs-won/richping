$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$runtimePath = Join-Path $projectRoot "var"
New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null
$lockPath = Join-Path $runtimePath "daily.lock"
try {
    $jobLock = [System.IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
} catch {
    Write-Error "Another daily job is already running."
    exit 1
}
try {
    # Native stderr also contains successful structured logs in PowerShell.
    $ErrorActionPreference = "Continue"
    & $pythonPath -m richping daily 2>&1 | Tee-Object -FilePath (Join-Path $runtimePath "daily.log") -Append
    $jobExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = "Stop"
    $jobLock.Dispose()
}
exit $jobExit
