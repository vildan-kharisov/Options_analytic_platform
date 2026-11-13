# MOEX Options Analytic Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python: 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-teal.svg)](https://www.postgresql.org/)

> **Платформа для сбора, обработки и визуализации рыночных данных по опционам Московской Биржи** с ETL-конвейером, аналитическим дашбордом и rule-based рекомендательной системой опционных стратегий.

---

## 📋 Содержание

- [Архитектура](#-архитектура)
- [Стек технологий](#-стек-технологий)
- [Что уже реализовано](#-что-уже-реализовано)
- [ETL-конвейеры](#etl-конвейеры)
- [API](#api)
- [Дашборд](#-дашборд)
- [Portfolio Lab](#portfolio-lab)
- [Recommendation Engine (RECOM)](#recommendation-engine-recom)
- [Быстрый старт](#-быстрый-старт)
- [Структура проекта](#-структура-проекта)
- [Дорожная карта](#-дорожная-карта)

---

## 🏗 Архитектура

```
┌──────────────────────────────────────────────────────────────┐
│                    Apache Airflow (ETL)                       │
│  ┌────────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │ market_history │ │option_std    │ │volatility_curve    │  │
│  │_hv_etl          │ │_etl          │ │_etl                │  │
│  └────────────────┘ └──────────────┘ └────────────────────┘  │
│  ┌────────────────┐ ┌──────────────┐                         │
│  │option_vol_etl  │ │option_vol_   │                         │
│  │                │ │plus_etl      │                         │
│  └────────────────┘ └──────────────┘                         │
└──────────────────────┬───────────────────────────────────────┘
                       │ PostgreSQL (192.168.1.100:5430)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    Flask REST API                             │
│  /api/assets   /api/board   /api/curve   /api/iv   /api/hv  │
│  /api/v1/dashboard/*  /api/v1/portfolios/*                   │
│  /api/v1/recom/*                                              │
└──────────────────────┬───────────────────────────────────────┘
                       │ JSON
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                  ECharts Dashboard (Browser)                  │
│  OHLC + Bands  │  HV/IV  │  Volatility Smile  │  Greeks     │
│  Term Structure│  Portfolio Lab  │  RECOM Recommendations  │
└──────────────────────────────────────────────────────────────┘
```

---

## 🛠 Стек технологий

| Слой | Технологии |
|------|-----------|
| **ETL** | Apache Airflow, Python, `requests`, `psycopg2`, NumPy |
| **Хранилище** | PostgreSQL 14+, Materialized Views, Triggers |
| **API** | Flask, Flask-CORS, Named SQL queries |
| **Frontend** | HTML5, JavaScript, Apache ECharts |
| **ML** | scikit-learn (GradientBoostingRegressor), rule-based engine |
| **DevOps** | Docker, Git, PowerShell |

---

## ✅ Что уже реализовано

### 1. ETL-конвейеры (5 DAGs)

| DAG | Источник | Таблица | Расписание | Строк/запуск |
|-----|----------|---------|------------|-------------|
| `market_history_hv_etl` | MOEX History API | `market_history` | Пн-Пт 07:00 | 500–2000 |
| `option_volatility_etl` | MOEX Option-Calc API | `option_volatility` | Пн-Пт 10:00–18:00 | 50–100 |
| `option_volatility_plus_etl` | MOEX Option-Calc API | `option_volatility_plus` | Пн-Пт 10:00–18:00 | 50–100 |
| `volatility_curve_etl` | MOEX Option-Calc API | `volatility_curve` | Пн-Пт 07:00–16:00 | 200–500 |
| `option_std_etl` | MOEX Option-Calc API | `option_std` | Пн-Пт 10:00–18:00 | 200–500 |

**Ключевые особенности ETL:**
- Пагинация и обработка ошибок MOEX ISS API
- Upsert-паттерн: `DELETE + INSERT` по дате (replace daily partition)
- Расчёт HV-10/20/30 через скользящее стандартное отклонение лог-доходностей
- Retry (2 попытки, 10 мин задержка), детальное логирование

### 2. Моделирование данных в PostgreSQL

**ETL-таблицы (5):**
- `market_history` — котировки фьючерсов + HV
- `option_std` — полная опционная доска (страйки + Greeks)
- `option_volatility` — IV по центральному страйку
- `option_volatility_plus` — расширенная IV + bid/offer + теоретические цены
- `volatility_curve` — кривая strike-volatility

**Витринные views (4):**
- `v_market_history_norm` — нормализация `asset` → `asset_code`
- `v_option_std_latest` — последний срез optionboard
- `v_option_volatility_plus_latest` — последний срез расширенной IV
- `v_iv_next_month` / `v_hv_iv_daily` — IV следующего месяца + IV-HV spread

**Прикладная схема Portfolio Lab (4 таблицы):**
- `portfolio`, `portfolio_leg`, `portfolio_snapshot`, `scenario_run`
- Триггеры `updated_at`, constraint-валидация, JSONB для детализации

### 3. Flask REST API (~800 строк, 20+ эндпоинтов)

**REST-эндпоинты:**
```
GET  /api/assets          # Список активов
GET  /api/board           # Опционная доска (страйки + Greeks)
GET  /api/curve           # Кривая волатильности
GET  /api/iv              # IV по сериям
GET  /api/hv              # Историческая волатильность

GET  /api/v1/dashboard/ohlc         # OHLC + exp_std bands
GET  /api/v1/dashboard/hv-iv        # HV/IV time series
GET  /api/v1/dashboard/smile        # Volatility smile
GET  /api/v1/dashboard/greeks       # Delta/Gamma/Vega/Theta
GET  /api/v1/dashboard/oi           # Open Interest proxy

POST /api/v1/portfolios             # Создать портфель
GET  /api/v1/portfolios/{id}/legs   # Ноги портфеля
POST /api/v1/portfolios/{id}/valuate# Оценка + Greeks
GET  /api/v1/portfolios/{id}/payoff # Payoff на экспирацию

GET  /api/v1/recom/strategies       # Рекомендации стратегий
GET  /api/v1/recom/backtest/run     # Backtest симуляция
```

**SQL-слой:** Named queries в `sql/api/echarts_api.sql` — все SQL-запросы вынесены из Python, единый источник истины.

### 4. ECharts Dashboard

Интерактивные графики для 4 активов (SI, RTS, GOLD, BRENT):
- **OHLC** — свечной график с линиями стандартного отклонения
- **HV/IV** — временные ряды исторической и implied волатильности
- **Volatility Smile** — улыбка волатильности по сериям
- **Greeks** — Delta, Gamma, Vega, Theta по страйкам
- **Term Structure** — временная структура IV
- **Volatility Curve STD** — нормализованная кривая с WMA и доверительными интервалами

### 5. Portfolio Lab

Конструктор опционного портфеля:
- CRUD портфелей и ног (CALL/PUT/FUT)
- Оценка стоимости по 3 режимам: `mid`, `theoretical`, `entry`
- Агрегация Greeks с учётом BUY/SELL знака и lot_size
- Payoff-график на экспирацию через `generate_series()`
- Снапшоты оценки и история PnL

### 6. Recommendation Engine (RECOM)

**Rule-based engine** для 8 опционных стратегий:

| Стратегия | Сценарий |
|-----------|----------|
| Bull Call Spread | Умеренно бычий |
| Bear Put Spread | Умеренно медвежий |
| Iron Condor | Флэт + высокая IV |
| Iron Butterfly | Флэт + elevated IV |
| Long Straddle | Ожидание импульса + низкая IV |
| Long Strangle | Мощный импульс + дешёвый вход |
| Debit Put Spread | Защитный хедж хвостового риска |
| Calendar/Diagonal | Выраженная term structure |

**Pipeline рекомендаций:**
1. **Feature snapshot** — spot, HV, IV-Rank, Skew, Term Slope, Quote Fill
2. **Regime detection** — direction / vol / skew / term
3. **Candidate generation** — фильтрация по режиму
4. **Risk filtering** — по профилю (conservative/balanced/aggressive)
5. **Scoring** — 10+ весовая функция
6. **Position sizing (Stage 3)** — risk budget, liquidity scale
7. **Sanity checks** — vega/gamma caps, max-loss guard

**Гибридный ML-режим:**
- `GradientBoostingRegressor` для rerank кандидатов
- Out-of-time split (80/20 по датам)
- Метрики: MSE, MAE, Sign Hit Rate vs rule-baseline

**Backtesting framework:**
- Симуляция по горизонтам 1d/5d/10d/exp
- Метрики: win rate, drawdown, stability
- Breakdown по рыночным режимам

---

## 🚀 Быстрый старт

### Предусловия
- Python 3.14+
- PostgreSQL 14+ (сервер 192.168.1.100:5430)
- Apache Airflow (Docker)

### Запуск дашборда

```powershell
cd "F:\Algo\Options"
.\scripts\start-local-app.ps1
```

Это запускает:
1. Flask API на `http://localhost:5300`
2. Открывает `echarts_dashboard.html` в браузере

### Проверка API

```powershell
Invoke-RestMethod -Uri "http://localhost:5300/api/health"
```

### Запуск ETL

```powershell
# В Docker-контейнере Airflow
airflow dags test market_history_hv_etl "$(date -u +%Y-%m-%d)"
airflow dags test option_std_etl "$(date -u +%Y-%m-%d)"
```

---

## 📁 Структура проекта

```
Options/
├── airflow_*.py                  # ETL DAG-скрипты (локальные)
├── echarts_api.py                # Flask REST API
├── echarts_dashboard.html        # ECharts дашборд
├── dash_app.py                   # Dash/Plotly версия (альтернатива)
├── .env                          # DB credentials (не в git)
│
├── sql/
│   ├── api/echarts_api.sql       # Named SQL queries для API
│   ├── portfolio_schema.sql      # Portfolio Lab DDL
│   ├── views_market_inputs.sql   # Витринные views
│   └── queries_portfolio.sql     # Практические запросы
│
├── AirFlow-main/                 # submodule: RECOM engine + MLOps
│   ├── app/
│   │   ├── echarts_api.py        # RECOM API
│   │   └── recom_engine.py       # Rule-based + ML engine
│   ├── config/                   # Калибровка, strategy guide
│   └── docs/
│
├── js/
│   ├── api_client.js             # REST API client
│   └── state.js                  # Dashboard state management
│
├── scripts/
│   ├── start-local-app.ps1       # Запуск дашборда
│   └── stop-local-app.ps1        # Остановка
│
├── PROJECT.md                    # Полное описание проекта
├── PORTFOLIO_LAB_API_SCHEMA.md   # Схема Portfolio Lab
├── PLAN_OPTIONS.md              # Дорожная карта
├── INSTRUCTION.md               # Инструкция по запуску
└── README.md                     # Этот файл
```

---

## 🗺 Дорожная карта

### Этап 1: MVP ✅
- [x] ETL-конвейеры (5 DAGs)
- [x] PostgreSQL схема + views
- [x] Flask API (20+ эндпоинтов)
- [x] ECharts дашборд (6 графиков)
- [x] Portfolio Lab v1

### Этап 2: Расширенная аналитика
- [ ] IV Rank / IV Percentile (252d)
- [ ] IV-HV Spread + Z-score
- [ ] Skew индикатор
- [ ] Term Structure Heatmap
- [ ] Smile evolution (слайдер)
- [ ] Open Interest загрузка

### Этап 3: Production Ready
- [ ] Логирование в едином формате
- [ ] Retry/circuit-breaker для MOEX API
- [ ] Data quality checks
- [ ] Индексы и материализованные views
- [ ] Unit-тесты API

### Этап 4: Масштабирование
- [ ] Миграция Flask → FastAPI
- [ ] TimescaleDB для time-series
- [ ] CI/CD пайплайн
- [ ] Миграция ML в MLflow

---

## 📊 Ключевые метрики

| Метрика | Значение |
|---------|----------|
| Файлов в репозитории | 45 |
| Строк кода | ~10 200 |
| ETL DAGs | 5 |
| REST эндпоинтов | 20+ |
| Named SQL queries | 30+ |
| Опционных стратегий (RECOM) | 8 |
| Активов | SI, RTS, GOLD, BRENT |

---

## 👤 Автор

**Вилдан Харисов** — Data Engineer

- GitHub: [vildan-kharisov](https://github.com/vildan-kharisov)
- GitVerse: [vildan1980](https://gitverse.ru/vildan1980)
