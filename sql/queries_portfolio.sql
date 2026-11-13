-- Практические запросы для Portfolio Lab.
-- Формат параметров: PostgreSQL positional placeholders ($1, $2, ...).
-- Использование: через psycopg2/asyncpg с execute(sql, params).

-- =========================================================
-- Q1. Последний spot для актива
-- params:
--   $1 = asset_code (SI/RTS/GOLD/BRENT)
-- =========================================================
SELECT
    asset_code,
    today AS tradedate,
    last AS spot_last,
    settleprice
FROM (
    SELECT
        UPPER(asset) AS asset_code,
        tradedate AS today,
        last,
        settleprice,
        ROW_NUMBER() OVER (PARTITION BY UPPER(asset) ORDER BY tradedate DESC) AS rn
    FROM public.market_history
) t
WHERE t.asset_code = $1
  AND t.rn = 1;


-- =========================================================
-- Q2. Оценка ног портфеля (цена + Greeks из option_std)
-- params:
--   $1 = portfolio_id
--   $2 = use_latest_day (BOOLEAN). Обычно TRUE.
--   $3 = pricing_mode (TEXT): 'mid' | 'theoretical' | 'entry'
-- =========================================================
WITH p AS (
    SELECT id, asset_code
    FROM portfolio
    WHERE id = $1
),
latest_day AS (
    SELECT asset_code, MAX(today) AS mx_today
    FROM public.option_std
    GROUP BY asset_code
),
legs AS (
    SELECT
        l.*,
        p.asset_code
    FROM portfolio_leg l
    JOIN p ON p.id = l.portfolio_id
),
book AS (
    SELECT
        s.*
    FROM public.option_std s
    JOIN p ON p.asset_code = s.asset_code
    LEFT JOIN latest_day d ON d.asset_code = s.asset_code
    WHERE ($2 IS FALSE OR s.today = d.mx_today)
),
leg_marked AS (
    SELECT
        l.id AS leg_id,
        l.portfolio_id,
        l.side,
        l.instrument_type,
        l.qty,
        l.lot_size,
        l.entry_price,
        l.optionseries_code,
        l.strike,
        l.expiration_date,
        b.today,
        b.asset_code,
        b.futures_code,
        b.volatility,
        CASE WHEN l.instrument_type = 'CALL' THEN b.call_offer ELSE b.put_offer END AS offer_px,
        CASE WHEN l.instrument_type = 'CALL' THEN b.call_bid   ELSE b.put_bid   END AS bid_px,
        CASE WHEN l.instrument_type = 'CALL' THEN b.call_t_price ELSE b.put_t_price END AS theo_px,
        CASE WHEN l.instrument_type = 'CALL' THEN b.call_delta ELSE b.put_delta END AS delta,
        CASE WHEN l.instrument_type = 'CALL' THEN b.call_gamma ELSE b.put_gamma END AS gamma,
        CASE WHEN l.instrument_type = 'CALL' THEN b.call_vega  ELSE b.put_vega  END AS vega,
        CASE WHEN l.instrument_type = 'CALL' THEN b.call_theta ELSE b.put_theta END AS theta,
        CASE WHEN l.instrument_type = 'CALL' THEN b.call_rho   ELSE b.put_rho   END AS rho
    FROM legs l
    LEFT JOIN book b
           ON b.optionseries_code = l.optionseries_code
          AND b.strike = l.strike
          AND b.expiration_date = l.expiration_date
    WHERE l.instrument_type IN ('CALL', 'PUT')
),
leg_priced AS (
    SELECT
        leg_id,
        portfolio_id,
        side,
        qty,
        lot_size,
        today,
        COALESCE(
            CASE
                WHEN LOWER($3) = 'mid' THEN (offer_px + bid_px) / 2.0
                WHEN LOWER($3) = 'theoretical' THEN theo_px
                WHEN LOWER($3) = 'entry' THEN entry_price
                ELSE (offer_px + bid_px) / 2.0
            END,
            entry_price
        ) AS unit_price,
        delta,
        gamma,
        vega,
        theta,
        rho
    FROM leg_marked
)
SELECT
    portfolio_id,
    MAX(today) AS market_day,
    SUM((CASE WHEN side = 'BUY' THEN 1 ELSE -1 END) * qty * lot_size * unit_price) AS total_value,
    SUM((CASE WHEN side = 'BUY' THEN 1 ELSE -1 END) * qty * lot_size * delta) AS delta_total,
    SUM((CASE WHEN side = 'BUY' THEN 1 ELSE -1 END) * qty * lot_size * gamma) AS gamma_total,
    SUM((CASE WHEN side = 'BUY' THEN 1 ELSE -1 END) * qty * lot_size * vega)  AS vega_total,
    SUM((CASE WHEN side = 'BUY' THEN 1 ELSE -1 END) * qty * lot_size * theta) AS theta_total,
    SUM((CASE WHEN side = 'BUY' THEN 1 ELSE -1 END) * qty * lot_size * rho)   AS rho_total
FROM leg_priced
GROUP BY portfolio_id;


-- =========================================================
-- Q3. Быстрый payoff на экспирацию (без time value)
-- params:
--   $1 = portfolio_id
--   $2 = spot_from
--   $3 = spot_to
--   $4 = spot_step
-- =========================================================
WITH grid AS (
    SELECT generate_series($2::NUMERIC, $3::NUMERIC, $4::NUMERIC) AS spot
),
legs AS (
    SELECT
        l.id,
        l.portfolio_id,
        l.side,
        l.instrument_type,
        l.strike,
        l.qty,
        l.lot_size,
        COALESCE(l.entry_price, 0) AS entry_price
    FROM portfolio_leg l
    WHERE l.portfolio_id = $1
),
leg_payoff AS (
    SELECT
        g.spot,
        l.id AS leg_id,
        (
            CASE l.instrument_type
                WHEN 'CALL' THEN GREATEST(g.spot - l.strike, 0)
                WHEN 'PUT'  THEN GREATEST(l.strike - g.spot, 0)
                WHEN 'FUT'  THEN (g.spot - l.entry_price)
                ELSE 0
            END
            -
            CASE WHEN l.instrument_type IN ('CALL', 'PUT') THEN l.entry_price ELSE 0 END
        ) * l.qty * l.lot_size
        *
        (CASE WHEN l.side = 'BUY' THEN 1 ELSE -1 END) AS pnl_leg
    FROM grid g
    CROSS JOIN legs l
)
SELECT
    spot,
    SUM(pnl_leg) AS pnl_total
FROM leg_payoff
GROUP BY spot
ORDER BY spot;


-- =========================================================
-- Q4. Шаблон для записи snapshot
-- params:
--   $1 portfolio_id
--   $2 spot_price
--   $3 total_value
--   $4 pnl_abs
--   $5 pnl_pct
--   $6 delta_total
--   $7 gamma_total
--   $8 vega_total
--   $9 theta_total
--   $10 rho_total
--   $11 details_json (JSON)
-- =========================================================
INSERT INTO portfolio_snapshot (
    portfolio_id, spot_price, total_value, pnl_abs, pnl_pct,
    delta_total, gamma_total, vega_total, theta_total, rho_total, details_json
)
VALUES (
    $1, $2, $3, $4, $5,
    $6, $7, $8, $9, $10, $11::jsonb
)
RETURNING id, valuation_ts;


-- =========================================================
-- Q5. Шаблон для записи run сценариев
-- params:
--   $1 portfolio_id
--   $2 spot_from
--   $3 spot_to
--   $4 spot_step
--   $5 vol_shift_from
--   $6 vol_shift_to
--   $7 vol_shift_step
--   $8 t_days
--   $9 result_json (JSON)
-- =========================================================
INSERT INTO scenario_run (
    portfolio_id,
    spot_from, spot_to, spot_step,
    vol_shift_from, vol_shift_to, vol_shift_step,
    t_days,
    result_json
)
VALUES (
    $1,
    $2, $3, $4,
    $5, $6, $7,
    $8,
    $9::jsonb
)
RETURNING id, run_ts;
