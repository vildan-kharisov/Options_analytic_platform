# PLAN_OPTIONS_CHECKLIST.md

Статусы:
- `[ ]` TODO
- `[-]` IN_PROGRESS
- `[x]` DONE

---

## Этап 0. Фиксация текущей базы проекта

- [x] Реализованы ETL/DAG для `option_volatility`, `option_volatility_plus`, `option_std`, `volatility_curve`, `market_history`
- [x] Развернут ECharts-дашборд (`echarts_api.py` + `echarts_dashboard.html`)
- [x] Добавлены инструменты рисования на графиках (гор./верт. линии + очистка)
- [x] Подготовлен документ `PORTFOLIO_LAB_API_SCHEMA.md`
- [x] Подготовлен SQL-пакет (`sql/portfolio_schema.sql`, `sql/views_market_inputs.sql`, `sql/queries_portfolio.sql`)
- [x] Обновлен `PROJECT.md` рекомендациями по графикам и структуре вкладок
- [x] Сформирован roadmap `PLAN_OPTIONS.md`

---

## Workflow: локальное приложение + удаленный ETL/DB

- [x] Зафиксирован подход: сервер `192.168.1.100` используется только для ETL (Airflow) и PostgreSQL
- [x] Зафиксирован подход: UI/API запускаются локально на рабочей машине
- [x] `echarts_api.py` переведен на чтение параметров подключения из `.env`
- [x] Добавлен локальный health endpoint: `/api/health`
- [x] Добавлен PowerShell-скрипт запуска: `scripts/start-local-app.ps1`
- [x] Добавить отдельный PowerShell-скрипт остановки локальных процессов (`echarts_api`)
- [x] Убрать дубли/старые блоки из `INSTRUCTION.md`, оставить единый актуальный сценарий запуска
- [ ] Проверить сетевой доступ к PostgreSQL с локальной машины (firewall/pg_hba)
- [ ] Зафиксировать регламент выката ETL на сервер: `dev -> test DAG run -> prod`

---

## Этап 1. MVP (стабильный аналитический дашборд)

### 1.1 Данные и SQL
- [x] Применить `sql/portfolio_schema.sql` в целевой БД
- [x] Применить `sql/views_market_inputs.sql` в целевой БД
- [x] Проверить маппинг `market_history.asset` ↔ `asset_code`
- [x] Вынести SQL текущих endpoint в отдельные `.sql` файлы (без SQL-строк в коде)
- [x] Добавить health endpoint `/api/health`

### 1.2 API (Flask)
- [x] Унифицировать формат ответов API (`ok/data/meta/error`)
- [x] Разделить endpoint по доменам: OHLC, HV/IV, Smile, Term Structure, Greeks
- [x] Добавить валидацию входных параметров (`asset`, `date`, `series`)
- [x] Централизовать логику `MAX(today)` и fallback для пустых данных

### 1.3 Frontend (ECharts)
- [x] Разбить JS-логику на модули: API-клиент / state / render
- [x] Привести все вкладки активов к общему шаблону
- [x] Добавить отображение даты среза на графиках
- [x] Добавить единый loader + fallback «нет данных»
- [x] Зафиксировать поведение линий при перезагрузке вкладки

### 1.4 Acceptance для MVP
- [x] Все графики из `PROJECT.md` работают для `SI/RTS/GOLD/BRENT`
- [x] API не падает на пустых/неполных данных
- [x] Обновления ETL отображаются в UI без ручных правок

---

## Этап 2. MVP+ (расширенная волатильностная аналитика)

### 2.1 Новые графики и метрики
- [ ] Добавить `IV Rank / IV Percentile (252d)`
- [ ] Добавить `IV - HV (10/20/30) + Z-score`
- [ ] Добавить `Skew` (`IV put_25Δ - IV call_25Δ`)
- [ ] Добавить `Term Structure Heatmap`
- [ ] Добавить `Smile evolution` (слайдер/анимация по датам)
- [ ] Добавить `Open Interest by Strike + ΔOI + PCR`

### 2.2 Источник OI
- [ ] Подтвердить источник OI через ISS API (приоритет 1)
- [ ] Реализовать fallback-источник (MOEX pages parser), если ISS недостаточен
- [ ] Создать таблицу `option_oi_history`
- [ ] Создать DAG для обновления OI

### 2.3 Acceptance для MVP+
- [ ] Все 6 новых графиков работают для 4 активов
- [ ] OI обновляется минимум 1 раз в торговый день
- [ ] Формулы/логика расчета описаны в документации

---

## Этап 3. Portfolio Lab v1

### 3.1 Backend API
- [ ] Реализовать CRUD для портфелей: `/api/v1/portfolios`
- [ ] Реализовать CRUD для ног: `/api/v1/portfolios/{id}/legs`
- [ ] Реализовать `/api/v1/portfolios/{id}/valuate`
- [ ] Реализовать `/api/v1/portfolios/{id}/scenarios/run`
- [ ] Реализовать `/api/v1/portfolios/{id}/scenarios/latest`

### 3.2 Расчетная логика
- [ ] Реализовать приоритет цен: `mid -> theoretical -> entry_price`
- [ ] Реализовать агрегирование Greeks с учетом `BUY/SELL`, `qty`, `lot_size`
- [ ] Реализовать payoff на экспирацию
- [ ] Реализовать сценарную сетку `spot shift x vol shift`
- [ ] Сохранять результаты в `portfolio_snapshot` и `scenario_run`

### 3.3 Frontend Portfolio Lab
- [ ] Добавить вкладку/секцию `Portfolio Lab` в UI
- [ ] Добавить форму создания портфеля
- [ ] Добавить редактор ног (таблица + add/remove/edit)
- [ ] Добавить графики `Payoff`, `Scenario Heatmap`, `Greeks`
- [ ] Добавить экспорт/импорт стратегии (JSON)

### 3.4 Acceptance для Portfolio Lab v1
- [ ] Портфель можно создать и сохранить
- [ ] Ноги можно добавлять/удалять/редактировать
- [ ] Оценка и сценарии считаются и отображаются
- [ ] Результаты сохраняются в БД

---

## Этап 4. Production Ready

### 4.1 Надежность
- [ ] Единый формат логирования API/ETL
- [ ] Retry/timeout для вызовов MOEX
- [ ] Уведомления о сбоях DAG (Airflow notifications)
- [ ] Data quality checks (пропуски, аномалии IV/HV)

### 4.2 Производительность
- [ ] Добавить/проверить индексы под основные запросы
- [ ] Добавить кэширование тяжелых endpoint (опционально Redis)
- [ ] Добавить материализованные витрины для heatmap/skew/rank

### 4.3 Тестирование
- [ ] Unit-тесты SQL/бизнес-логики
- [ ] Интеграционные тесты API ↔ DB ↔ ETL
- [ ] Smoke-тест после каждого обновления ETL

### 4.4 Acceptance для Production Ready
- [ ] Система перезапускается без ручной отладки
- [ ] Ошибки и сбои отслеживаются через логи/алерты
- [ ] Время ответа стабильно при росте истории

---

## Этап 5. Масштабирование

### 5.1 Технологии
- [ ] Подготовить миграцию `Flask -> FastAPI` (без ломки `/api/v1`)
- [ ] Оценить `TimescaleDB` для длинных временных рядов
- [ ] Определить целевой frontend-путь: модульный HTML/JS или `React + ECharts`

### 5.2 Продуктовые функции
- [ ] Шаблоны стратегий (presets)
- [ ] История сделок + PnL attribution
- [ ] Сравнение нескольких портфелей
- [ ] Отчеты и выгрузки (CSV/Excel/PDF)

### 5.3 DevOps/команда
- [ ] Разделить окружения `dev/test/prod`
- [ ] Внедрить CI/CD (lint, tests, deploy)
- [ ] Добавить ролевую модель и доступы пользователей

---

## Ближайший спринт (рекомендуемый старт)

- [x] Применить SQL: `portfolio_schema.sql` + `views_market_inputs.sql`
- [x] Добавить `/api/v1/health`
- [x] Реализовать `POST /api/v1/portfolios`
- [x] Реализовать `POST /api/v1/portfolios/{id}/valuate`
- [x] Добавить MVP-блок `Portfolio Lab` в `echarts_dashboard.html` (таблица ног + payoff)
- [x] Провести end-to-end проверку: ETL → API → UI

