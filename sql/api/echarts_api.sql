-- name: health_ping
SELECT 1 AS ok;

-- name: assets_market_history
SELECT DISTINCT UPPER(asset) AS asset FROM {table} ORDER BY asset;

-- name: assets_asset_code
SELECT DISTINCT asset_code AS asset FROM {table} ORDER BY asset_code;

-- name: dates_market_history
SELECT DISTINCT tradedate AS dt FROM {table} ORDER BY tradedate DESC LIMIT 30;

-- name: dates_today
SELECT DISTINCT today AS dt FROM {table} ORDER BY today DESC LIMIT 30;

-- name: series_by_asset
SELECT DISTINCT optionseries_code AS s
FROM {table}
WHERE asset_code = %s
  AND (%s IS NULL OR today = %s)
ORDER BY s;

-- name: board_max_today
SELECT MAX(today) AS d FROM option_std WHERE asset_code = %s;

-- name: board_default_series
SELECT DISTINCT optionseries_code AS s
FROM option_std
WHERE asset_code = %s AND today = %s
ORDER BY s
LIMIT 1;

-- name: board_rows
SELECT strike, volatility, central_strike,
       call_offer, call_bid, call_delta, call_gamma, call_vega, call_theta,
       put_offer, put_bid, put_delta, put_gamma, put_vega, put_theta
FROM option_std
WHERE asset_code = %s AND optionseries_code = %s AND today = %s
ORDER BY strike;

-- name: curve_max_today
SELECT MAX(today) AS d FROM volatility_curve WHERE asset_code = %s;

-- name: curve_rows
SELECT optionseries_code, strike, volatility, central_strike, series_type, expiration_date
FROM volatility_curve
WHERE asset_code = %s AND today = %s
ORDER BY optionseries_code, strike;

-- name: iv_max_today
SELECT MAX(today) AS d FROM option_volatility WHERE asset_code = %s;

-- name: iv_rows
SELECT optionseries_code, volatility, expiration_date, central_strike, series_type, futures_code
FROM option_volatility
WHERE asset_code = %s AND today = %s
ORDER BY expiration_date;

-- name: hv_rows
SELECT tradedate, secid, open, high, low, last,
       settleprice, voltoday, openposition, hv_10, hv_20, hv_30
FROM market_history
WHERE UPPER(asset) = UPPER(%s)
ORDER BY tradedate;

-- name: portfolios_get_all
SELECT id, name, asset_code, currency, created_at, updated_at
FROM portfolio
ORDER BY updated_at DESC, id DESC;

-- name: portfolios_get_by_asset
SELECT id, name, asset_code, currency, created_at, updated_at
FROM portfolio
WHERE asset_code = %s
ORDER BY updated_at DESC, id DESC;

-- name: portfolios_insert
INSERT INTO portfolio (name, asset_code, currency)
VALUES (%s, %s, %s)
RETURNING id, name, asset_code, currency, created_at, updated_at;

-- name: portfolio_legs_get
SELECT id, portfolio_id, side, instrument_type, optionseries_code, futures_code,
       strike, expiration_date, qty, lot_size, entry_price, implied_vol, updated_at
FROM portfolio_leg
WHERE portfolio_id = %s
ORDER BY id;

-- name: portfolio_payoff
WITH grid AS (
    SELECT generate_series(%s::NUMERIC, %s::NUMERIC, %s::NUMERIC) AS spot
),
legs AS (
    SELECT id, side, instrument_type, strike, qty, lot_size, COALESCE(entry_price, 0) AS entry_price
    FROM portfolio_leg
    WHERE portfolio_id = %s
),
leg_payoff AS (
    SELECT
        g.spot,
        (
            CASE l.instrument_type
                WHEN 'CALL' THEN GREATEST(g.spot - l.strike, 0)
                WHEN 'PUT'  THEN GREATEST(l.strike - g.spot, 0)
                WHEN 'FUT'  THEN (g.spot - l.entry_price)
                ELSE 0
            END
            - CASE WHEN l.instrument_type IN ('CALL', 'PUT') THEN l.entry_price ELSE 0 END
        ) * l.qty * l.lot_size
        * (CASE WHEN l.side = 'BUY' THEN 1 ELSE -1 END) AS pnl_leg
    FROM grid g
    CROSS JOIN legs l
)
SELECT spot, SUM(pnl_leg) AS pnl_total
FROM leg_payoff
GROUP BY spot
ORDER BY spot;

-- name: portfolio_spot_last
SELECT last AS spot_last
FROM (
    SELECT UPPER(asset) AS asset_code, tradedate, last,
           ROW_NUMBER() OVER (PARTITION BY UPPER(asset) ORDER BY tradedate DESC) AS rn
    FROM public.market_history
) t
WHERE t.asset_code = (SELECT asset_code FROM portfolio WHERE id = %s)
  AND t.rn = 1;

-- name: portfolio_valuate_agg
WITH p AS (
    SELECT id, asset_code
    FROM portfolio
    WHERE id = %s
),
latest_day AS (
    SELECT asset_code, MAX(today) AS mx_today
    FROM public.option_std
    GROUP BY asset_code
),
legs AS (
    SELECT l.*, p.asset_code
    FROM portfolio_leg l
    JOIN p ON p.id = l.portfolio_id
),
book AS (
    SELECT s.*
    FROM public.option_std s
    JOIN p ON p.asset_code = s.asset_code
    LEFT JOIN latest_day d ON d.asset_code = s.asset_code
    WHERE (%s IS FALSE OR s.today = d.mx_today)
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
        portfolio_id,
        side,
        qty,
        lot_size,
        today,
        COALESCE(
            CASE
                WHEN %s = 'mid' THEN (offer_px + bid_px) / 2.0
                WHEN %s = 'theoretical' THEN theo_px
                WHEN %s = 'entry' THEN entry_price
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

-- name: portfolio_entry_value
SELECT SUM((CASE WHEN side='BUY' THEN 1 ELSE -1 END) * qty * lot_size * COALESCE(entry_price, 0)) AS entry_value
FROM portfolio_leg
WHERE portfolio_id = %s;

-- name: portfolio_snapshot_insert
INSERT INTO portfolio_snapshot (
    portfolio_id, spot_price, total_value, pnl_abs, pnl_pct,
    delta_total, gamma_total, vega_total, theta_total, rho_total, details_json
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
RETURNING id, valuation_ts;

-- name: dashboard_ohlc_bands
SELECT
    hv.tradedate,
    hv.open,
    hv.high,
    hv.low,
    hv.last,
    iv.exp_std,
    (hv.last + iv.exp_std) AS up,
    (hv.last - iv.exp_std) AS down
FROM public.market_history hv
LEFT JOIN public.option_volatility_plus iv
       ON UPPER(hv.asset) = iv.asset_code
      AND UPPER(hv.secid) = iv.futures_code
      AND hv.tradedate = iv.today
      AND iv.series_type = 'Q'
WHERE UPPER(hv.asset) = UPPER(%s)
ORDER BY hv.tradedate;

-- name: dashboard_hv_iv
SELECT
    mh.tradedate,
    mh.hv_10,
    mh.hv_20,
    mh.hv_30,
    iv.iv_next_month
FROM (
    SELECT UPPER(asset) AS asset_code, tradedate, hv_10, hv_20, hv_30
    FROM public.market_history
) mh
LEFT JOIN (
    WITH src AS (
        SELECT
            ov.asset_code,
            ov.today,
            ov.volatility AS iv_next_month,
            ROW_NUMBER() OVER (
                PARTITION BY ov.asset_code, ov.today
                ORDER BY ov.expiration_date
            ) AS rn
        FROM public.option_volatility ov
        WHERE ov.series_type IN ('Q', 'M')
          AND DATE_TRUNC('month', ov.expiration_date) = DATE_TRUNC('month', ov.today + INTERVAL '1 month')
    )
    SELECT asset_code, today, iv_next_month
    FROM src
    WHERE rn = 1
) iv
  ON iv.asset_code = mh.asset_code
 AND iv.today = mh.tradedate
WHERE mh.asset_code = UPPER(%s)
ORDER BY mh.tradedate;

-- name: dashboard_time_structure
SELECT optionseries_code, futures_code, central_strike, series_type, volatility, expiration_date
FROM public.option_volatility v
WHERE v.asset_code = %s
  AND v.today = (
      SELECT MAX(t.today) FROM public.option_volatility t WHERE t.asset_code = v.asset_code
  )
ORDER BY expiration_date;

-- name: dashboard_series_latest
SELECT DISTINCT optionseries_code AS s
FROM public.option_std
WHERE asset_code = %s
  AND today = (SELECT MAX(today) FROM public.option_std WHERE asset_code = %s)
ORDER BY s;

-- name: dashboard_smile_multi
SELECT optionseries_code, strike, volatility, central_strike, series_type
FROM public.option_std
WHERE asset_code = %s
  AND today = (SELECT MAX(today) FROM public.option_std WHERE asset_code = %s)
  AND (%s = '' OR optionseries_code = ANY(string_to_array(%s, ',')))
ORDER BY optionseries_code, strike;

-- name: dashboard_greeks
SELECT
    strike, volatility, central_strike,
    call_delta, call_gamma, call_vega, call_theta,
    put_delta, put_gamma, put_vega, put_theta
FROM public.option_std
WHERE asset_code = %s
  AND optionseries_code = %s
  AND today = (SELECT MAX(today) FROM public.option_std WHERE asset_code = %s)
ORDER BY strike;

-- name: dashboard_oi_proxy
SELECT
    strike,
    call_numtrds,
    put_numtrds,
    COALESCE(call_numtrds, 0) + COALESCE(put_numtrds, 0) AS total_numtrds
FROM public.option_std
WHERE asset_code = %s
  AND optionseries_code = %s
  AND today = (SELECT MAX(today) FROM public.option_std WHERE asset_code = %s)
ORDER BY strike;

-- name: dashboard_curve_std_normal
WITH latest_day AS (
    SELECT MAX(today)::date AS mx_today
    FROM public.option_std
    WHERE asset_code = %s
),
base AS (
    SELECT
        s.futures_code,
        s.optionseries_code,
        s.series_type,
        s.central_strike,
        s.strike,
        s.volatility,
        s.call_delta,
        s.put_delta,
        s.expiration_date,
        s.today::date AS today,
        ABS(0.25 - s.call_delta) AS call_25,
        MIN(ABS(0.25 - s.call_delta)) OVER (PARTITION BY s.today) AS min_call_25,
        ABS(0.10 - s.call_delta) AS call_10,
        MIN(ABS(0.10 - s.call_delta)) OVER (PARTITION BY s.today) AS min_call_10,
        ABS(0.05 - s.call_delta) AS call_5,
        MIN(ABS(0.05 - s.call_delta)) OVER (PARTITION BY s.today) AS min_call_5,
        ABS(0.25 + s.put_delta) AS put_25,
        MIN(ABS(0.25 + s.put_delta)) OVER (PARTITION BY s.today) AS min_put_25,
        ABS(0.10 + s.put_delta) AS put_10,
        MIN(ABS(0.10 + s.put_delta)) OVER (PARTITION BY s.today) AS min_put_10,
        ABS(0.05 + s.put_delta) AS put_5,
        MIN(ABS(0.05 + s.put_delta)) OVER (PARTITION BY s.today) AS min_put_5
    FROM public.option_std s
    WHERE s.asset_code = %s
      AND s.series_type IN ('Q', 'M')
      AND DATE_TRUNC('month', s.expiration_date) = DATE_TRUNC('month', s.today + INTERVAL '1 month')
      AND s.today::date BETWEEN (SELECT mx_today - INTERVAL '365 days' FROM latest_day) AND (SELECT mx_today FROM latest_day)
),
typed AS (
    SELECT
        futures_code,
        optionseries_code,
        series_type,
        volatility,
        expiration_date,
        today,
        CASE
            WHEN min_call_25 = call_25 THEN 'call_25'
            WHEN min_call_10 = call_10 THEN 'call_10'
            WHEN min_call_5 = call_5 THEN 'call_5'
            WHEN min_put_25 = put_25 THEN 'put_25'
            WHEN min_put_10 = put_10 THEN 'put_10'
            WHEN min_put_5 = put_5 THEN 'put_5'
            WHEN central_strike = strike THEN 'center'
        END AS delta_type
    FROM base
    WHERE min_call_25 = call_25
       OR min_call_10 = call_10
       OR min_call_5 = call_5
       OR min_put_25 = put_25
       OR min_put_10 = put_10
       OR min_put_5 = put_5
       OR central_strike = strike
),
ratio AS (
    SELECT
        futures_code,
        optionseries_code,
        series_type,
        delta_type,
        ROUND(
            volatility / NULLIF(
                MAX(CASE WHEN delta_type = 'center' THEN volatility END) OVER (PARTITION BY today),
                0
            ),
            4
        ) AS delta_ratio,
        ROW_NUMBER() OVER (PARTITION BY delta_type ORDER BY today ASC) AS weights,
        today
    FROM typed
),
stats AS (
    SELECT
        delta_type,
        delta_ratio,
        weights,
        today,
        COALESCE(
            STDDEV(delta_ratio) OVER (
                PARTITION BY delta_type ORDER BY today ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ),
            0
        ) AS std,
        LAST_VALUE(delta_ratio) OVER (
            PARTITION BY delta_type ORDER BY today ASC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS last_val
    FROM ratio
),
agg AS (
    SELECT
        delta_type,
        CASE
            WHEN delta_type = 'put_5' THEN 0
            WHEN delta_type = 'put_10' THEN 1
            WHEN delta_type = 'put_25' THEN 2
            WHEN delta_type = 'center' THEN 3
            WHEN delta_type = 'call_25' THEN 4
            WHEN delta_type = 'call_10' THEN 5
            WHEN delta_type = 'call_5' THEN 6
        END AS num,
        MAX(last_val) AS current_value,
        ROUND(SUM(delta_ratio * weights) / NULLIF(SUM(weights), 0), 4) AS wma,
        ROUND(SUM(std * weights) / NULLIF(SUM(weights), 0), 4) AS std_wma
    FROM stats
    GROUP BY delta_type
)
SELECT
    a.delta_type,
    a.num,
    a.current_value,
    a.wma,
    a.std_wma,
    ROUND(a.wma * (1 + a.std_wma), 4) AS up,
    ROUND(a.wma * (1 - a.std_wma), 4) AS down,
    (SELECT mx_today FROM latest_day) AS today_max
FROM agg a
ORDER BY a.num;
