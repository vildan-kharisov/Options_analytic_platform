# Portfolio Lab: API и схема данных

Документ описывает целевую модель для блока моделирования опционного портфеля: хранение ног, оценка Greeks/PnL, сценарные расчеты и быстрый доступ из UI.

---

## 1) Минимальная схема БД (PostgreSQL)

```sql
-- 1. Портфели пользователя
CREATE TABLE IF NOT EXISTS portfolio (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    asset_code      VARCHAR(16) NOT NULL,      -- SI / RTS / GOLD / BRENT
    currency        VARCHAR(8) NOT NULL DEFAULT 'RUB',
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_portfolio_asset_code ON portfolio(asset_code);

-- 2. Ноги портфеля (позиции)
CREATE TABLE IF NOT EXISTS portfolio_leg (
    id                  BIGSERIAL PRIMARY KEY,
    portfolio_id        BIGINT NOT NULL REFERENCES portfolio(id) ON DELETE CASCADE,
    side                VARCHAR(8) NOT NULL CHECK (side IN ('BUY','SELL')),
    instrument_type     VARCHAR(8) NOT NULL CHECK (instrument_type IN ('CALL','PUT','FUT')),
    optionseries_code   VARCHAR(64),            -- для опциона
    futures_code        VARCHAR(64),            -- для фьючерса
    strike              NUMERIC,                -- для опциона
    expiration_date     DATE,                   -- для опциона
    qty                 NUMERIC NOT NULL,       -- количество контрактов
    lot_size            NUMERIC NOT NULL DEFAULT 1,
    entry_price         NUMERIC,                -- цена входа (опцион/фьючерс)
    implied_vol         NUMERIC,                -- IV, если фиксируем вручную
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_portfolio_leg_pid ON portfolio_leg(portfolio_id);
CREATE INDEX IF NOT EXISTS ix_portfolio_leg_series ON portfolio_leg(optionseries_code, expiration_date);

-- 3. Снимок оценки портфеля (кэш расчета)
CREATE TABLE IF NOT EXISTS portfolio_snapshot (
    id                  BIGSERIAL PRIMARY KEY,
    portfolio_id        BIGINT NOT NULL REFERENCES portfolio(id) ON DELETE CASCADE,
    valuation_ts        TIMESTAMP NOT NULL DEFAULT NOW(),
    spot_price          NUMERIC NOT NULL,
    total_value         NUMERIC,
    pnl_abs             NUMERIC,
    pnl_pct             NUMERIC,
    delta_total         NUMERIC,
    gamma_total         NUMERIC,
    vega_total          NUMERIC,
    theta_total         NUMERIC,
    rho_total           NUMERIC,
    details_json        JSONB                   -- оценка по ногам/промежуточные поля
);

CREATE INDEX IF NOT EXISTS ix_portfolio_snapshot_pid_ts ON portfolio_snapshot(portfolio_id, valuation_ts DESC);

-- 4. Результаты сценариев (heatmap / срезы)
CREATE TABLE IF NOT EXISTS scenario_run (
    id                  BIGSERIAL PRIMARY KEY,
    portfolio_id        BIGINT NOT NULL REFERENCES portfolio(id) ON DELETE CASCADE,
    run_ts              TIMESTAMP NOT NULL DEFAULT NOW(),
    spot_from           NUMERIC NOT NULL,
    spot_to             NUMERIC NOT NULL,
    spot_step           NUMERIC NOT NULL,
    vol_shift_from      NUMERIC NOT NULL,       -- в долях, например -0.20
    vol_shift_to        NUMERIC NOT NULL,       -- +0.20
    vol_shift_step      NUMERIC NOT NULL,
    t_days              INTEGER NOT NULL DEFAULT 0,
    result_json         JSONB NOT NULL          -- матрица PnL/Greeks
);

CREATE INDEX IF NOT EXISTS ix_scenario_run_pid_ts ON scenario_run(portfolio_id, run_ts DESC);
```

Примечание: таблицы `portfolio*` и `scenario_run` — прикладной слой Portfolio Lab.  
Они не создаются текущими DAG в `AirFlow-main` и должны поддерживаться API-приложением.

---

## 2) Источники рыночных данных для расчетов

- `public.option_std` (DAG `option_std_etl`) — полная опционная доска по страйкам:
  `asset_code, futures_code, optionseries_code, central_strike, series_type, strike, volatility,`
  `call_offer/call_bid, put_offer/put_bid, call_* greeks, put_* greeks, expiration_date, today`.
- `public.option_volatility` (DAG `option_volatility_etl`) — IV по центральному страйку:
  `asset_code, futures_code, optionseries_code, central_strike, series_type, volatility, expiration_date, today`.
- `public.option_volatility_plus` (DAG `option_volatility_plus_etl`) — расширенная IV-таблица по центральному страйку:
  `exp_std` + `call_*`/`put_*` (включая Greeks, bid/offer, теоретические цены, numtrades).
- `public.market_history` (DAG `market_history_hv_etl`) — спот и история волатильности:
  `asset` (важно: не `asset_code`), `secid, open, high, low, last, settleprice, voltoday, openposition, tradedate, hv_10, hv_20, hv_30`.
- `public.volatility_curve` (DAG `volatility_curve_etl`) — кривая `strike-volatility` по серии:
  `asset_code, optionseries_code, series_type, strike, central_strike, volatility, expiration_date, today`.
- MOEX option-calc API — расчетные параметры и синтетические сценарии (при необходимости).

### 2.1 Маппинг кодов актива (обязательно)

В API-слое используем единый параметр `asset_code` (`SI/RTS/GOLD/BRENT`), но:
- в `option_*` и `volatility_curve` поле называется `asset_code`;
- в `market_history` поле называется `asset`.

Нужен явный маппинг в SQL/репозитории, чтобы фильтры не расходились.

Рекомендуемый приоритет ценообразования ноги:
1. mid = `(offer + bid) / 2`, если доступны обе стороны.
2. fallback: `t_price` (теоретическая) из `option_std`.
3. fallback: последняя сохраненная `entry_price`.

---

## 3) API-контракт (Flask/FastAPI)

Базовый префикс: `/api/v1`

### 3.1 Портфели

- `GET /api/v1/portfolios?asset=SI`
- `POST /api/v1/portfolios`
- `GET /api/v1/portfolios/{id}`
- `PATCH /api/v1/portfolios/{id}`
- `DELETE /api/v1/portfolios/{id}`

Пример тела `POST /api/v1/portfolios`:

```json
{
  "name": "SI Calendar Hedge",
  "asset_code": "SI",
  "currency": "RUB"
}
```

### 3.2 Ноги портфеля

- `GET /api/v1/portfolios/{id}/legs`
- `POST /api/v1/portfolios/{id}/legs`
- `PATCH /api/v1/portfolios/{id}/legs/{leg_id}`
- `DELETE /api/v1/portfolios/{id}/legs/{leg_id}`

Пример тела `POST /api/v1/portfolios/{id}/legs`:

```json
{
  "side": "BUY",
  "instrument_type": "CALL",
  "optionseries_code": "Si-3.26M210326CA80000",
  "futures_code": "SiH6",
  "strike": 80000,
  "expiration_date": "2026-03-21",
  "qty": 10,
  "lot_size": 1,
  "entry_price": 1250,
  "implied_vol": null
}
```

### 3.3 Оценка и Greeks

- `POST /api/v1/portfolios/{id}/valuate`
  - Считает текущую стоимость, PnL и агрегированные Greeks.
  - Сохраняет запись в `portfolio_snapshot`.

Пример тела:

```json
{
  "pricing_mode": "mid",
  "use_live_spot": true,
  "spot_override": null,
  "vol_shift": 0.0,
  "r_rate": 0.16
}
```

Пример ответа:

```json
{
  "portfolio_id": 12,
  "valuation_ts": "2026-02-10T12:30:00Z",
  "spot_price": 98765.4,
  "total_value": 154320.2,
  "pnl_abs": 5320.1,
  "pnl_pct": 3.57,
  "greeks": {
    "delta": -12.3,
    "gamma": 0.024,
    "vega": 51.7,
    "theta": -840.6,
    "rho": 15.9
  },
  "legs": []
}
```

### 3.4 Сценарии (PnL / Greeks grid)

- `POST /api/v1/portfolios/{id}/scenarios/run`
- `GET /api/v1/portfolios/{id}/scenarios/latest`
- `GET /api/v1/portfolios/{id}/scenarios/{run_id}`

Пример тела `run`:

```json
{
  "spot_from": -0.15,
  "spot_to": 0.15,
  "spot_step": 0.01,
  "vol_shift_from": -0.20,
  "vol_shift_to": 0.20,
  "vol_shift_step": 0.02,
  "t_days": 7,
  "metric": "pnl_abs"
}
```

---

## 4) Эндпоинты для UI-графиков

Для прямой интеграции в ECharts:

- `GET /api/v1/assets`
- `GET /api/v1/{asset}/ohlc?from=YYYY-MM-DD&to=YYYY-MM-DD`
- `GET /api/v1/{asset}/hv-iv?series_type=Q,M&next_month=true`
- `GET /api/v1/{asset}/smile?series=...&date=YYYY-MM-DD`
- `GET /api/v1/{asset}/smile/multi-series?date=YYYY-MM-DD&series=...&series=...`
- `GET /api/v1/{asset}/term-structure?date=YYYY-MM-DD`
- `GET /api/v1/{asset}/oi?series=...&date=YYYY-MM-DD`

Возвращать уже подготовленные структуры:
- `x`: массив оси X
- `series`: массив серий для ECharts
- `meta`: служебные поля (asset, date, source, warnings)

---

## 5) Бизнес-правила расчета (рекомендовано)

- Для вкладки актива использовать единый фильтр `asset_code`, но для `market_history` маппить его на поле `asset`.
- Для “next month IV” использовать `option_volatility` или `option_volatility_plus`:
  `series_type IN ('Q','M')` и `expiration_date` следующего календарного месяца.
- Для улыбки фиксировать единый `today`, иначе кривые нельзя корректно сравнивать.
- Для текущего среза данных использовать `MAX(today)` в таблицах `option_std`, `option_volatility`, `option_volatility_plus`, `volatility_curve`.
- Для HV использовать явное окно (`hv_10` / `hv_20` / `hv_30`), по умолчанию рекомендуется `hv_20`.
- Для Greeks портфеля соблюдать знак:
  - `BUY` = `+1`
  - `SELL` = `-1`
- Все денежные поля отдавать в валюте портфеля (`currency`), при необходимости конвертировать.

---

## 6) План внедрения (без большого рефакторинга)

1. Создать таблицы `portfolio`, `portfolio_leg`, `portfolio_snapshot`, `scenario_run`.
2. Добавить CRUD API портфелей и ног.
3. Добавить `valuate` на текущем `Flask` с использованием данных из `option_std`/`market_history`.
4. Добавить `scenarios/run` и heatmap-график в `echarts_dashboard.html`.
5. После стабилизации вынести API в `FastAPI` (опционально), не меняя контракты.

---

## 7) PowerShell примеры запуска

```powershell
# API (текущий проект)
python .\echarts_api.py

# Проверка health (если добавить endpoint /api/v1/health)
Invoke-RestMethod -Uri "http://localhost:5300/api/v1/health" -Method Get

# Пример вызова оценки портфеля
$body = @{
  pricing_mode = "mid"
  use_live_spot = $true
  spot_override = $null
  vol_shift = 0.0
  r_rate = 0.16
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5300/api/v1/portfolios/12/valuate" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```
