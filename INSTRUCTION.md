# Инструкция по запуску и остановке (актуальная)

## Целевая схема работы

- Сервер `192.168.1.100` используется только для:
  - ETL (Airflow / `AirFlow-main`)
  - PostgreSQL
- Приложение запускается локально на вашей машине:
  - `echarts_api.py`
  - `echarts_dashboard.html`

## Предусловия

- В файле `.env` заполнены параметры:
  - `POSTGRES_HOST=192.168.1.100`
  - `POSTGRES_PORT=5430`
  - `POSTGRES_DB=...`
  - `POSTGRES_USER=...`
  - `POSTGRES_PASSWORD=...`
  - `API_PORT=5300`
- Установлены Python-пакеты: `flask`, `flask-cors`, `psycopg2`.

---

## Запуск приложения (рекомендуется)

```powershell
cd "d:\Algo\Options"
.\scripts\start-local-app.ps1
```

Что делает скрипт:
- запускает локальный API (`python echarts_api.py`) в отдельном окне PowerShell;
- открывает `echarts_dashboard.html` в браузере.

Запуск API без открытия дашборда:

```powershell
cd "d:\Algo\Options"
.\scripts\start-local-app.ps1 -NoOpenDashboard
```

Проверка состояния API:

```powershell
Invoke-RestMethod -Uri "http://localhost:5300/api/health" -Method Get
```

---

## Остановка приложения (рекомендуется)

```powershell
powershell -ExecutionPolicy Bypass -File "d:\Algo\Options\scripts\stop-local-app.ps1"
```

Также можно закрыть вручную:
- вкладку браузера (`Ctrl+W`);
- окно PowerShell с API (`Ctrl+C`).

---

## Аварийная остановка всех Python-процессов

Использовать только если действительно нужно:

```powershell
Stop-Process -Name python -Force
```

# 1) Синхронизация из рабочей папки в репо
powershell -ExecutionPolicy Bypass -File "D:\Algo\Options\AirFlow-main\scripts\sync-workspace-to-repo.ps1" -VerboseOutput

# 2) Проверка
git -C "D:\Algo\Options\AirFlow-main" status -sb

# 3) Дальше commit/push как обычно
git -C "D:\Algo\Options\AirFlow-main" add .
git -C "D:\Algo\Options\AirFlow-main" commit -m "Ваш коммит"
git -C "D:\Algo\Options\AirFlow-main" push