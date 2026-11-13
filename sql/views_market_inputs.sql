-- Views для нормализации ETL-таблиц под Portfolio Lab.
-- Основная цель: единый asset_code + быстрый доступ к последнему срезу.

BEGIN;

-- 1) Нормализованный market_history: asset -> asset_code.
CREATE OR REPLACE VIEW v_market_history_norm AS
SELECT
    id,
    UPPER(asset) AS asset_code,
    asset,
    secid,
    tradedate,
    open,
    high,
    low,
    last,
    settleprice,
    voltoday,
    openposition,
    hv_10,
    hv_20,
    hv_30
FROM public.market_history;

-- 2) Последний срез option_std по активу.
CREATE OR REPLACE VIEW v_option_std_latest AS
WITH latest_day AS (
    SELECT asset_code, MAX(today) AS mx_today
    FROM public.option_std
    GROUP BY asset_code
)
SELECT s.*
FROM public.option_std s
JOIN latest_day d
  ON d.asset_code = s.asset_code
 AND d.mx_today = s.today;

-- 3) Последний срез option_volatility_plus по активу.
CREATE OR REPLACE VIEW v_option_volatility_plus_latest AS
WITH latest_day AS (
    SELECT asset_code, MAX(today) AS mx_today
    FROM public.option_volatility_plus
    GROUP BY asset_code
)
SELECT v.*
FROM public.option_volatility_plus v
JOIN latest_day d
  ON d.asset_code = v.asset_code
 AND d.mx_today = v.today;

-- 4) IV следующего месяца (Q/M) по центральному страйку.
-- Используется для графика HV/IV и сигналов IV-HV spread.
CREATE OR REPLACE VIEW v_iv_next_month AS
WITH src AS (
    SELECT
        ov.asset_code,
        ov.futures_code,
        ov.optionseries_code,
        ov.series_type,
        ov.central_strike,
        ov.volatility,
        ov.expiration_date,
        ov.today,
        ROW_NUMBER() OVER (
            PARTITION BY ov.asset_code, ov.today
            ORDER BY ov.expiration_date
        ) AS rn
    FROM public.option_volatility ov
    WHERE ov.series_type IN ('Q', 'M')
      AND DATE_TRUNC('month', ov.expiration_date) = DATE_TRUNC('month', ov.today + INTERVAL '1 month')
)
SELECT
    asset_code,
    futures_code,
    optionseries_code,
    series_type,
    central_strike,
    volatility AS iv_next_month,
    expiration_date,
    today
FROM src
WHERE rn = 1;

-- 5) Объединенный вью для HV/IV по дате.
CREATE OR REPLACE VIEW v_hv_iv_daily AS
SELECT
    mh.asset_code,
    mh.tradedate AS today,
    mh.hv_10,
    mh.hv_20,
    mh.hv_30,
    iv.iv_next_month,
    (iv.iv_next_month - mh.hv_20) AS iv_hv20_spread
FROM v_market_history_norm mh
LEFT JOIN v_iv_next_month iv
       ON iv.asset_code = mh.asset_code
      AND iv.today = mh.tradedate;

COMMIT;
