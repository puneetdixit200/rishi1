param(
    [int]$RestartDelaySeconds = 2
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$python = Join-Path $backendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Backend virtual environment not found at $python. Create backend/.venv first."
}

Write-Host "Starting HC1 Local Sync Worker with development crash-restart policy."
Write-Host "Press Ctrl+C for graceful shutdown."

while ($true) {
    Push-Location $backendDir
    try {
        & $python -m app.workers.sync_worker
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if ($exitCode -eq 0) {
        Write-Host "Sync worker stopped cleanly."
        break
    }

    Write-Warning "Sync worker exited with code $exitCode. Restarting in $RestartDelaySeconds second(s)."
    Start-Sleep -Seconds $RestartDelaySeconds
}
