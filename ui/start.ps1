Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$uiRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $uiRoot

try {
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installing UI dependencies..."
        npm.cmd install
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }

    npm.cmd run dev
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}