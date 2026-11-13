"""Flask API — отдаёт данные из PostgreSQL для ECharts-дашборда."""

import os
import json
import re
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import psycopg2.extras

app = Flask(__name__)
CORS(app)


def _load_env_file(path: str = ".env") -> None:
    """
    Минимальный парсер .env без внешних зависимостей.
    Поддерживает форматы:
      KEY=value
      KEY: value
    """
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue

        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()

DB = dict(
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=int(os.getenv("POSTGRES_PORT", "5430")),
    dbname=os.getenv("POSTGRES_DB", "postgres"),
    user=os.getenv("POSTGRES_USER", "postgres"),
    password=os.getenv("POSTGRES_PASSWORD", "mysecretpassword"),
)
API_PORT = int(os.getenv("API_PORT", "5300"))
SQL_FILE = Path("sql/api/echarts_api.sql")
ALLOWED_TABLES = {"option_std", "volatility_curve", "option_volatility", "option_volatility_plus", "market_history"}
ASSET_RE = re.compile(r"^[A-Z0-9_]+$")
SERIES_RE = re.compile(r"^[A-Za-z0-9._:\-]+$")


def _load_named_sql(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"SQL-файл не найден: {path}")
    queries = {}
    current_name = None
    buf = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("-- name:"):
            if current_name:
                queries[current_name] = "\n".join(buf).strip()
            current_name = raw.split(":", 1)[1].strip()
            buf = []
        elif current_name:
            buf.append(raw)
    if current_name:
        queries[current_name] = "\n".join(buf).strip()
    return queries


SQL = _load_named_sql(SQL_FILE)


def sql(name: str) -> str:
    if name not in SQL:
        raise KeyError(f"SQL query '{name}' not found in {SQL_FILE}")
    return SQL[name]


def _safe_table(table_name: str, fallback: str = "option_std") -> str:
    tbl = (table_name or fallback).strip()
    return tbl if tbl in ALLOWED_TABLES else fallback


def ok(data=None, meta=None):
    payload = {"ok": True, "data": data}
    if meta is not None:
        payload["meta"] = meta
    return jsonify(payload)


def fail(error: str, status: int = 400):
    return jsonify({"ok": False, "error": error}), status


def _validate_asset(value: str, required: bool = True):
    asset = (value or "").strip().upper()
    if not asset and not required:
        return None, None
    if not asset:
        return None, "Параметр 'asset' обязателен"
    if not ASSET_RE.match(asset):
        return None, "Некорректный формат asset"
    return asset, None


def _validate_date(value: str, required: bool = False):
    dt = (value or "").strip()
    if not dt and not required:
        return None, None
    if not dt:
        return None, "Параметр 'date' обязателен"
    try:
        datetime.strptime(dt, "%Y-%m-%d")
    except Exception:
        return None, "Некорректный формат date. Ожидается YYYY-MM-DD"
    return dt, None


def _validate_series(value: str, required: bool = False):
    s = (value or "").strip()
    if not s and not required:
        return None, None
    if not s:
        return None, "Параметр 'series' обязателен"
    if not SERIES_RE.match(s):
        return None, "Некорректный формат series"
    return s, None


def _validate_series_csv(value: str):
    raw = (value or "").strip()
    if not raw:
        return "", None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return "", None
    for p in parts:
        if not SERIES_RE.match(p):
            return None, "Некорректный формат series списка"
    return ",".join(parts), None


def _resolve_today(asset: str, supplied_date: str, max_query_name: str):
    if supplied_date:
        return supplied_date
    r = q(sql(max_query_name), (asset,))
    return r[0]["d"] if r else None


def q(sql, params=None):
    conn = psycopg2.connect(**DB)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [{k: (str(v) if hasattr(v, 'isoformat') else v) for k, v in r.items()} for r in rows]
    finally:
        conn.close()


def _safe_float(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except Exception:
        return None


@app.route("/api/assets")
def assets():
    tbl = _safe_table(request.args.get("table"), "option_std")
    query = sql("assets_market_history") if tbl == "market_history" else sql("assets_asset_code")
    return ok(q(query.format(table=tbl)), {"table": tbl})


@app.route("/api/dates")
def dates():
    tbl = _safe_table(request.args.get("table"), "option_std")
    query = sql("dates_market_history") if tbl == "market_history" else sql("dates_today")
    return ok(q(query.format(table=tbl)), {"table": tbl})


@app.route("/api/series")
def series():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    dt, err = _validate_date(request.args.get("date"), required=False)
    if err:
        return fail(err)
    tbl = _safe_table(request.args.get("table"), "option_std")
    rows = q(sql("series_by_asset").format(table=tbl), (asset, dt, dt))
    return ok(rows, {"table": tbl, "asset": asset, "date": dt})


@app.route("/api/board")
def board():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    series, err = _validate_series(request.args.get("series"), required=False)
    if err:
        return fail(err)
    supplied_dt, err = _validate_date(request.args.get("date"), required=False)
    if err:
        return fail(err)
    dt = _resolve_today(asset, supplied_dt, "board_max_today")
    if not series and dt:
        r = q(sql("board_default_series"), (asset, dt))
        series = r[0]["s"] if r else None
    if not dt or not series:
        return ok([], {"asset": asset, "today": dt, "series": series})
    rows = q(sql("board_rows"), (asset, series, dt))
    return ok(rows, {"asset": asset, "today": dt, "series": series})


@app.route("/api/curve")
def curve():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    supplied_dt, err = _validate_date(request.args.get("date"), required=False)
    if err:
        return fail(err)
    dt = _resolve_today(asset, supplied_dt, "curve_max_today")
    if not dt:
        return ok([], {"asset": asset, "today": None})
    rows = q(sql("curve_rows"), (asset, dt))
    return ok(rows, {"asset": asset, "today": dt})


@app.route("/api/iv")
def iv():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    supplied_dt, err = _validate_date(request.args.get("date"), required=False)
    if err:
        return fail(err)
    dt = _resolve_today(asset, supplied_dt, "iv_max_today")
    if not dt:
        return ok([], {"asset": asset, "today": None})
    return ok(q(sql("iv_rows"), (asset, dt)), {"asset": asset, "today": dt})


@app.route("/api/hv")
def hv():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    return ok(q(sql("hv_rows"), (asset,)), {"asset": asset})


@app.route("/api/health")
def health():
    try:
        rows = q(sql("health_ping"))
        db_ok = bool(rows and rows[0].get("ok") == 1)
        return ok({
            "service": "echarts_api",
            "db_ok": db_ok,
            "db_host": DB["host"],
            "db_port": DB["port"],
            "db_name": DB["dbname"],
        })
    except Exception as exc:
        return fail(str(exc), 500)


@app.route("/api/v1/health")
def health_v1():
    try:
        rows = q(sql("health_ping"))
        db_ok = bool(rows and rows[0].get("ok") == 1)
        return ok({
            "service": "echarts_api",
            "db_ok": db_ok,
            "db_host": DB["host"],
            "db_port": DB["port"],
            "db_name": DB["dbname"],
        })
    except Exception as exc:
        return fail(str(exc), 500)


@app.route("/api/v1/options/assets")
def options_assets_v1():
    tbl = _safe_table(request.args.get("table"), "option_std")
    if tbl == "market_history":
        return fail("Для options/assets используйте option_* или volatility_curve", 400)
    return ok(q(sql("assets_asset_code").format(table=tbl)), {"table": tbl, "domain": "options"})


@app.route("/api/v1/options/series")
def options_series_v1():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    dt, err = _validate_date(request.args.get("date"), required=False)
    if err:
        return fail(err)
    tbl = _safe_table(request.args.get("table"), "option_std")
    rows = q(sql("series_by_asset").format(table=tbl), (asset, dt, dt))
    return ok(rows, {"domain": "options", "table": tbl, "asset": asset, "today": dt})


@app.route("/api/v1/options/board")
def options_board_v1():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    series, err = _validate_series(request.args.get("series"), required=False)
    if err:
        return fail(err)
    supplied_dt, err = _validate_date(request.args.get("date"), required=False)
    if err:
        return fail(err)
    dt = _resolve_today(asset, supplied_dt, "board_max_today")
    if not series and dt:
        r = q(sql("board_default_series"), (asset, dt))
        series = r[0]["s"] if r else None
    if not dt or not series:
        return ok([], {"domain": "options", "asset": asset, "today": dt, "series": series})
    rows = q(sql("board_rows"), (asset, series, dt))
    return ok(rows, {"domain": "options", "asset": asset, "today": dt, "series": series})


@app.route("/api/v1/options/curve")
def options_curve_v1():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    supplied_dt, err = _validate_date(request.args.get("date"), required=False)
    if err:
        return fail(err)
    dt = _resolve_today(asset, supplied_dt, "curve_max_today")
    if not dt:
        return ok([], {"domain": "options", "asset": asset, "today": None})
    rows = q(sql("curve_rows"), (asset, dt))
    return ok(rows, {"domain": "options", "asset": asset, "today": dt})


@app.route("/api/v1/options/iv")
def options_iv_v1():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    supplied_dt, err = _validate_date(request.args.get("date"), required=False)
    if err:
        return fail(err)
    dt = _resolve_today(asset, supplied_dt, "iv_max_today")
    if not dt:
        return ok([], {"domain": "options", "asset": asset, "today": None})
    rows = q(sql("iv_rows"), (asset, dt))
    return ok(rows, {"domain": "options", "asset": asset, "today": dt})


@app.route("/api/v1/market/assets")
def market_assets_v1():
    rows = q(sql("assets_market_history").format(table="market_history"))
    return ok(rows, {"domain": "market", "table": "market_history"})


@app.route("/api/v1/market/hv")
def market_hv_v1():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    rows = q(sql("hv_rows"), (asset,))
    return ok(rows, {"domain": "market", "asset": asset})


@app.route("/api/v1/dashboard/ohlc")
def dashboard_ohlc_v1():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    rows = q(sql("dashboard_ohlc_bands"), (asset,))
    return ok(rows, {"domain": "dashboard", "asset": asset})


@app.route("/api/v1/dashboard/hv-iv")
def dashboard_hv_iv_v1():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    rows = q(sql("dashboard_hv_iv"), (asset,))
    return ok(rows, {"domain": "dashboard", "asset": asset})


@app.route("/api/v1/dashboard/curve")
def dashboard_curve_v1():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    rows = q(sql("dashboard_curve_std_normal"), (asset, asset))
    today_max = rows[0].get("today_max") if rows else None
    return ok(rows, {"domain": "dashboard", "asset": asset, "today": today_max})


@app.route("/api/v1/dashboard/time-structure")
def dashboard_time_structure_v1():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    rows = q(sql("dashboard_time_structure"), (asset,))
    return ok(rows, {"domain": "dashboard", "asset": asset})


@app.route("/api/v1/dashboard/series")
def dashboard_series_v1():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    rows = q(sql("dashboard_series_latest"), (asset, asset))
    return ok(rows, {"domain": "dashboard", "asset": asset})


@app.route("/api/v1/dashboard/smile")
def dashboard_smile_v1():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    series_csv, err = _validate_series_csv(request.args.get("series"))
    if err:
        return fail(err)
    rows = q(sql("dashboard_smile_multi"), (asset, asset, series_csv, series_csv))
    return ok(rows, {"domain": "dashboard", "asset": asset})


@app.route("/api/v1/dashboard/greeks")
def dashboard_greeks_v1():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    series, err = _validate_series(request.args.get("series"), required=True)
    if err:
        return fail(err)
    rows = q(sql("dashboard_greeks"), (asset, series, asset))
    return ok(rows, {"domain": "dashboard", "asset": asset, "series": series})


@app.route("/api/v1/dashboard/oi")
def dashboard_oi_v1():
    asset, err = _validate_asset(request.args.get("asset", "SI"))
    if err:
        return fail(err)
    series, err = _validate_series(request.args.get("series"), required=True)
    if err:
        return fail(err)
    rows = q(sql("dashboard_oi_proxy"), (asset, series, asset))
    return ok(rows, {"domain": "dashboard", "asset": asset, "series": series, "note": "OI proxy via numtrades"})


@app.route("/api/v1/portfolios", methods=["GET", "POST"])
def portfolios_v1():
    if request.method == "GET":
        asset, err = _validate_asset(request.args.get("asset"), required=False)
        if err:
            return fail(err)
        if asset:
            rows = q(sql("portfolios_get_by_asset"), (asset,))
        else:
            rows = q(sql("portfolios_get_all"))
        return ok(rows, {"asset": asset})

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    asset_code = (payload.get("asset_code") or "").strip().upper()
    currency = (payload.get("currency") or "RUB").strip().upper()

    if not name:
        return fail("Поле 'name' обязательно", 400)
    if asset_code not in {"SI", "RTS", "GOLD", "BRENT"}:
        return fail("asset_code должен быть одним из: SI, RTS, GOLD, BRENT", 400)

    row = q(sql("portfolios_insert"), (name, asset_code, currency))[0]
    return ok(row), 201


@app.route("/api/v1/portfolios/<int:portfolio_id>/legs", methods=["GET"])
def portfolio_legs_v1(portfolio_id: int):
    rows = q(sql("portfolio_legs_get"), (portfolio_id,))
    return ok(rows, {"portfolio_id": portfolio_id})


@app.route("/api/v1/portfolios/<int:portfolio_id>/payoff", methods=["GET"])
def portfolio_payoff_v1(portfolio_id: int):
    spot_from = request.args.get("spot_from", type=float, default=50000.0)
    spot_to = request.args.get("spot_to", type=float, default=150000.0)
    spot_step = request.args.get("spot_step", type=float, default=2500.0)
    if spot_step <= 0:
        return fail("spot_step должен быть > 0", 400)

    rows = q(sql("portfolio_payoff"), (spot_from, spot_to, spot_step, portfolio_id))
    return ok(rows, {"portfolio_id": portfolio_id, "spot_from": spot_from, "spot_to": spot_to, "spot_step": spot_step})


@app.route("/api/v1/portfolios/<int:portfolio_id>/valuate", methods=["POST"])
def portfolio_valuate_v1(portfolio_id: int):
    payload = request.get_json(silent=True) or {}
    pricing_mode = str(payload.get("pricing_mode", "mid")).lower()
    use_latest_day = bool(payload.get("use_latest_day", True))

    if pricing_mode not in {"mid", "theoretical", "entry"}:
        return fail("pricing_mode должен быть: mid/theoretical/entry", 400)

    spot_override = payload.get("spot_override")
    if spot_override is not None:
        spot_price = _safe_float(spot_override)
    else:
        spot_rows = q(sql("portfolio_spot_last"), (portfolio_id,))
        spot_price = _safe_float(spot_rows[0]["spot_last"]) if spot_rows else None

    agg_rows = q(sql("portfolio_valuate_agg"), (portfolio_id, use_latest_day, pricing_mode, pricing_mode, pricing_mode))

    if not agg_rows:
        return ok({
            "portfolio_id": portfolio_id,
            "snapshot_id": None,
            "valuation_ts": None,
            "spot_price": spot_price,
            "total_value": 0.0,
            "pnl_abs": 0.0,
            "pnl_pct": None,
            "greeks": {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0},
            "empty_portfolio": True,
        })

    agg = agg_rows[0]
    total_value = _safe_float(agg.get("total_value")) or 0.0
    entry_rows = q(sql("portfolio_entry_value"), (portfolio_id,))
    entry_value = _safe_float(entry_rows[0].get("entry_value")) if entry_rows else 0.0
    entry_value = entry_value or 0.0
    pnl_abs = total_value - entry_value
    pnl_pct = (pnl_abs / abs(entry_value) * 100.0) if entry_value else None

    details = {
        "pricing_mode": pricing_mode,
        "use_latest_day": use_latest_day,
        "market_day": agg.get("market_day"),
    }
    snap = q(sql("portfolio_snapshot_insert"), (
        portfolio_id,
        spot_price,
        total_value,
        pnl_abs,
        pnl_pct,
        agg.get("delta_total"),
        agg.get("gamma_total"),
        agg.get("vega_total"),
        agg.get("theta_total"),
        agg.get("rho_total"),
        json.dumps(details),
    ))[0]

    return ok({
        "portfolio_id": portfolio_id,
        "snapshot_id": snap.get("id"),
        "valuation_ts": snap.get("valuation_ts"),
        "spot_price": spot_price,
        "total_value": total_value,
        "pnl_abs": pnl_abs,
        "pnl_pct": pnl_pct,
        "greeks": {
            "delta": _safe_float(agg.get("delta_total")),
            "gamma": _safe_float(agg.get("gamma_total")),
            "vega": _safe_float(agg.get("vega_total")),
            "theta": _safe_float(agg.get("theta_total")),
            "rho": _safe_float(agg.get("rho_total")),
        },
    })


if __name__ == "__main__":
    app.run(debug=True, port=API_PORT)
