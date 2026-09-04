Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$uiRoot = Join-Path $root "ui"
$runRoot = Join-Path $root ".run"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment not found. Run: py -3.12 -m venv .venv"
}

if (-not (Test-Path -LiteralPath (Join-Path $uiRoot "node_modules"))) {
    throw "UI dependencies not found. Run: Set-Location ui; npm install"
}

New-Item -ItemType Directory -Force -Path $runRoot | Out-Null

$apiListener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
$uiListener = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue

if (-not $apiListener) {
    $apiProcess = Start-Process `
        -FilePath $python `
        -ArgumentList "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $root `
        -RedirectStandardOutput (Join-Path $runRoot "api.log") `
        -RedirectStandardError (Join-Path $runRoot "api-error.log") `
        -PassThru
    $apiProcess.Id | Set-Content -LiteralPath (Join-Path $runRoot "api.pid")
}

if (-not $uiListener) {
    $uiProcess = Start-Process `
        -FilePath $env:ComSpec `
        -ArgumentList "/c", "npm.cmd run dev" `
        -WorkingDirectory $uiRoot `
        -RedirectStandardOutput (Join-Path $runRoot "ui.log") `
        -RedirectStandardError (Join-Path $runRoot "ui-error.log") `
        -PassThru
    $uiProcess.Id | Set-Content -LiteralPath (Join-Path $runRoot "ui.pid")
}

$deadline = (Get-Date).AddSeconds(30)
do {
    Start-Sleep -Milliseconds 500
    try {
        $apiHealth = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "http://127.0.0.1:8000/health" `
            -TimeoutSec 2
        $uiHealth = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "http://127.0.0.1:5173" `
            -TimeoutSec 2
    }
    catch {
        $apiHealth = $null
        $uiHealth = $null
    }
    $servicesReady = ($null -ne $apiHealth -and $apiHealth.StatusCode -eq 200 -and $null -ne $uiHealth -and $uiHealth.StatusCode -eq 200)
} until ($servicesReady -or (Get-Date) -ge $deadline)

if (-not $apiHealth -or $apiHealth.StatusCode -ne 200) {
    throw "API failed to start. Check .run\api-error.log."
}

if (-not $uiHealth -or $uiHealth.StatusCode -ne 200) {
    throw "UI failed to start. Check .run\ui-error.log."
}

Write-Host "API: http://127.0.0.1:8000"
Write-Host "UI:  http://127.0.0.1:5173"
