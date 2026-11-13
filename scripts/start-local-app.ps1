Param(
    [switch]$NoOpenDashboard
)

$ErrorActionPreference = "Stop"

$projectRoot = "d:\Algo\Options"
Set-Location $projectRoot

Write-Host "[INFO] Starting local API..." -ForegroundColor Cyan

# Запуск API в отдельном окне PowerShell.
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$projectRoot'; python echarts_api.py"
)

Start-Sleep -Seconds 2

if (-not $NoOpenDashboard) {
    Write-Host "[INFO] Opening ECharts dashboard..." -ForegroundColor Cyan
    Start-Process "$projectRoot\echarts_dashboard.html"
}

Write-Host "[OK] Done. Health check: http://localhost:5300/api/health" -ForegroundColor Green

