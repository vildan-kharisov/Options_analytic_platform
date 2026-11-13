-- Portfolio Lab schema (PostgreSQL)
-- Назначение: прикладные таблицы для хранения портфелей, ног, снапшотов и сценариев.

BEGIN;

CREATE TABLE IF NOT EXISTS portfolio (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    asset_code      VARCHAR(16) NOT NULL CHECK (asset_code IN ('SI', 'RTS', 'GOLD', 'BRENT')),
    currency        VARCHAR(8) NOT NULL DEFAULT 'RUB',
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_portfolio_asset_code ON portfolio(asset_code);
CREATE INDEX IF NOT EXISTS ix_portfolio_updated_at ON portfolio(updated_at DESC);

CREATE TABLE IF NOT EXISTS portfolio_leg (
    id                  BIGSERIAL PRIMARY KEY,
    portfolio_id        BIGINT NOT NULL REFERENCES portfolio(id) ON DELETE CASCADE,
    side                VARCHAR(8) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    instrument_type     VARCHAR(8) NOT NULL CHECK (instrument_type IN ('CALL', 'PUT', 'FUT')),
    optionseries_code   VARCHAR(64),
    futures_code        VARCHAR(64),
    strike              NUMERIC,
    expiration_date     DATE,
    qty                 NUMERIC NOT NULL CHECK (qty > 0),
    lot_size            NUMERIC NOT NULL DEFAULT 1 CHECK (lot_size > 0),
    entry_price         NUMERIC,
    implied_vol         NUMERIC,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    -- Для опциона series/strike/exp обязательны, для фьючерса достаточно futures_code
    CONSTRAINT chk_portfolio_leg_option_fields CHECK (
        (instrument_type IN ('CALL', 'PUT') AND optionseries_code IS NOT NULL AND strike IS NOT NULL AND expiration_date IS NOT NULL)
        OR
        (instrument_type = 'FUT' AND futures_code IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS ix_portfolio_leg_pid ON portfolio_leg(portfolio_id);
CREATE INDEX IF NOT EXISTS ix_portfolio_leg_pid_updated ON portfolio_leg(portfolio_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_portfolio_leg_series ON portfolio_leg(optionseries_code, expiration_date);
CREATE INDEX IF NOT EXISTS ix_portfolio_leg_fut ON portfolio_leg(futures_code);

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
    details_json        JSONB
);

CREATE INDEX IF NOT EXISTS ix_portfolio_snapshot_pid_ts ON portfolio_snapshot(portfolio_id, valuation_ts DESC);

CREATE TABLE IF NOT EXISTS scenario_run (
    id                  BIGSERIAL PRIMARY KEY,
    portfolio_id        BIGINT NOT NULL REFERENCES portfolio(id) ON DELETE CASCADE,
    run_ts              TIMESTAMP NOT NULL DEFAULT NOW(),
    spot_from           NUMERIC NOT NULL,
    spot_to             NUMERIC NOT NULL,
    spot_step           NUMERIC NOT NULL CHECK (spot_step > 0),
    vol_shift_from      NUMERIC NOT NULL,
    vol_shift_to        NUMERIC NOT NULL,
    vol_shift_step      NUMERIC NOT NULL CHECK (vol_shift_step > 0),
    t_days              INTEGER NOT NULL DEFAULT 0 CHECK (t_days >= 0),
    result_json         JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_scenario_run_pid_ts ON scenario_run(portfolio_id, run_ts DESC);

-- Единая функция автопроставления updated_at.
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS portfolio_set_updated_at ON portfolio;
CREATE TRIGGER portfolio_set_updated_at
BEFORE UPDATE ON portfolio
FOR EACH ROW
EXECUTE FUNCTION trg_set_updated_at();

DROP TRIGGER IF EXISTS portfolio_leg_set_updated_at ON portfolio_leg;
CREATE TRIGGER portfolio_leg_set_updated_at
BEFORE UPDATE ON portfolio_leg
FOR EACH ROW
EXECUTE FUNCTION trg_set_updated_at();

COMMIT;
