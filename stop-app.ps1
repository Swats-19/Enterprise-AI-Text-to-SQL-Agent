Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runRoot = Join-Path $root ".run"

foreach ($service in "api", "ui") {
    $pidPath = Join-Path $runRoot "$service.pid"
    if (-not (Test-Path -LiteralPath $pidPath)) {
        continue
    }

    $processId = [int](Get-Content -LiteralPath $pidPath)
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $processId
        Write-Host "Stopped $service process $processId."
    }

    Remove-Item -LiteralPath $pidPath -Force
}
