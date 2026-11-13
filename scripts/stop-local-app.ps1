$ErrorActionPreference = "Stop"

Write-Host "[INFO] Останавливаю локальные процессы echarts_api.py..." -ForegroundColor Cyan

$targets = Get-CimInstance Win32_Process -Filter "name='python.exe'" |
    Where-Object { $_.CommandLine -like "*echarts_api.py*" }

if (-not $targets) {
    Write-Host "[INFO] Процессы echarts_api.py не найдены." -ForegroundColor Yellow
    exit 0
}

$targets | ForEach-Object {
    try {
        Stop-Process -Id $_.ProcessId -Force
        Write-Host ("[OK] Остановлен PID {0}" -f $_.ProcessId) -ForegroundColor Green
    }
    catch {
        Write-Host ("[WARN] Не удалось остановить PID {0}: {1}" -f $_.ProcessId, $_.Exception.Message) -ForegroundColor Yellow
    }
}

