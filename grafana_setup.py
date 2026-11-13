"""Скрипт для автоматической настройки Grafana: datasource + дашборды."""

import requests
import json

GRAFANA_URL = "http://localhost:3000"
AUTH = ("admin", "admin")
HEADERS = {"Content-Type": "application/json"}


def api(method, path, data=None):
    url = f"{GRAFANA_URL}{path}"
    r = requests.request(method, url, headers=HEADERS, auth=AUTH, json=data)
    print(f"  {method} {path} -> {r.status_code}")
    return r.json() if r.text else {}


# ═══════════════════════════════════════════════
#  1. DATASOURCE
# ═══════════════════════════════════════════════

print("=== Создание datasource ===")
ds = api("POST", "/api/datasources", {
    "name": "PostgreSQL",
    "type": "grafana-postgresql-datasource",
    "access": "proxy",
    "url": "host.docker.internal:7777",
    "database": "postgres",
    "user": "postgres",
    "secureJsonData": {"password": "mysecretpassword"},
    "jsonData": {
        "sslmode": "disable",
        "postgresVersion": 1500,
        "timescaledb": False,
    },
    "isDefault": True,
})
ds_uid = ds.get("datasource", {}).get("uid") or ds.get("uid", "")
print(f"  Datasource UID: {ds_uid}")

if not ds_uid:
    r = api("GET", "/api/datasources/name/PostgreSQL")
    ds_uid = r.get("uid", "")
    print(f"  Existing UID: {ds_uid}")

DS_UID = ds_uid


# ═══════════════════════════════════════════════
#  2. DASHBOARD
# ═══════════════════════════════════════════════

def sql_target(raw_sql, ref="A", format_type="table"):
    return {
        "refId": ref,
        "rawSql": raw_sql,
        "format": format_type,
        "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
    }


def time_series_panel(title, sql, grid_pos, y_label="", panel_id=1):
    return {
        "id": panel_id,
        "type": "timeseries",
        "title": title,
        "gridPos": grid_pos,
        "targets": [sql_target(sql, format_type="table")],
        "fieldConfig": {
            "defaults": {
                "custom": {"lineWidth": 2, "fillOpacity": 10, "spanNulls": True},
                "unit": y_label,
            },
            "overrides": [],
        },
        "options": {"legend": {"displayMode": "table", "placement": "bottom"}},
        "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
    }


def bar_chart_panel(title, sql, grid_pos, panel_id=1):
    return {
        "id": panel_id,
        "type": "barchart",
        "title": title,
        "gridPos": grid_pos,
        "targets": [sql_target(sql)],
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
        "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
    }


def table_panel(title, sql, grid_pos, panel_id=1):
    return {
        "id": panel_id,
        "type": "table",
        "title": title,
        "gridPos": grid_pos,
        "targets": [sql_target(sql)],
        "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
    }


def stat_panel(title, sql, grid_pos, panel_id=1):
    return {
        "id": panel_id,
        "type": "stat",
        "title": title,
        "gridPos": grid_pos,
        "targets": [sql_target(sql)],
        "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
    }


# ── Dashboard 1: Историческая волатильность ──

print("\n=== Dashboard: Историческая волатильность ===")

hv_panels = [
    time_series_panel(
        "HV 10 / 20 / 30",
        """SELECT tradedate AS "time", hv_10 AS "HV_10", hv_20 AS "HV_20", hv_30 AS "HV_30"
FROM market_history
WHERE asset = '$asset'
  AND tradedate BETWEEN '$__timeFrom()' AND '$__timeTo()'
ORDER BY tradedate""",
        {"x": 0, "y": 0, "w": 24, "h": 9},
        y_label="percent",
        panel_id=1,
    ),
    time_series_panel(
        "Цена закрытия (LAST)",
        """SELECT tradedate AS "time", last AS "LAST"
FROM market_history
WHERE asset = '$asset'
  AND tradedate BETWEEN '$__timeFrom()' AND '$__timeTo()'
ORDER BY tradedate""",
        {"x": 0, "y": 9, "w": 24, "h": 8},
        panel_id=2,
    ),
    time_series_panel(
        "Объём торгов",
        """SELECT tradedate AS "time", voltoday AS "Volume"
FROM market_history
WHERE asset = '$asset'
  AND tradedate BETWEEN '$__timeFrom()' AND '$__timeTo()'
ORDER BY tradedate""",
        {"x": 0, "y": 17, "w": 12, "h": 7},
        panel_id=3,
    ),
    time_series_panel(
        "Открытый интерес",
        """SELECT tradedate AS "time", openposition AS "OI"
FROM market_history
WHERE asset = '$asset'
  AND tradedate BETWEEN '$__timeFrom()' AND '$__timeTo()'
ORDER BY tradedate""",
        {"x": 12, "y": 17, "w": 12, "h": 7},
        panel_id=4,
    ),
    table_panel(
        "Данные",
        """SELECT tradedate, secid, open, high, low, last, settleprice,
       voltoday, openposition, hv_10, hv_20, hv_30
FROM market_history
WHERE asset = '$asset'
  AND tradedate BETWEEN '$__timeFrom()' AND '$__timeTo()'
ORDER BY tradedate DESC
LIMIT 50""",
        {"x": 0, "y": 24, "w": 24, "h": 8},
        panel_id=5,
    ),
]

hv_dashboard = {
    "dashboard": {
        "title": "Историческая волатильность (HV)",
        "tags": ["moex", "futures", "hv"],
        "timezone": "browser",
        "panels": hv_panels,
        "templating": {
            "list": [{
                "name": "asset",
                "type": "query",
                "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
                "query": "SELECT DISTINCT asset FROM market_history ORDER BY asset",
                "refresh": 1,
                "current": {"text": "Si", "value": "Si"},
            }]
        },
        "time": {"from": "2025-01-01T00:00:00Z", "to": "now"},
        "refresh": "",
    },
    "overwrite": True,
}
api("POST", "/api/dashboards/db", hv_dashboard)


# ── Dashboard 2: IV по сериям ──

print("\n=== Dashboard: IV по сериям ===")

iv_panels = [
    bar_chart_panel(
        "Временная структура IV",
        """SELECT expiration_date::text AS "Expiration", volatility AS "IV"
FROM option_volatility
WHERE asset_code = '$asset_code'
  AND today = (SELECT MAX(today) FROM option_volatility)
ORDER BY expiration_date""",
        {"x": 0, "y": 0, "w": 24, "h": 9},
        panel_id=1,
    ),
    table_panel(
        "Детали серий",
        """SELECT optionseries_code, futures_code, central_strike,
       series_type, volatility, expiration_date, today
FROM option_volatility
WHERE asset_code = '$asset_code'
  AND today = (SELECT MAX(today) FROM option_volatility)
ORDER BY expiration_date""",
        {"x": 0, "y": 9, "w": 24, "h": 8},
        panel_id=2,
    ),
    stat_panel(
        "Количество серий",
        """SELECT COUNT(*) AS "series_count"
FROM option_volatility
WHERE asset_code = '$asset_code'
  AND today = (SELECT MAX(today) FROM option_volatility)""",
        {"x": 0, "y": 17, "w": 6, "h": 4},
        panel_id=3,
    ),
    stat_panel(
        "Средняя IV",
        """SELECT ROUND(AVG(volatility)::numeric, 2) AS "avg_iv"
FROM option_volatility
WHERE asset_code = '$asset_code'
  AND today = (SELECT MAX(today) FROM option_volatility)""",
        {"x": 6, "y": 17, "w": 6, "h": 4},
        panel_id=4,
    ),
    stat_panel(
        "Дата данных",
        """SELECT MAX(today)::text AS "last_date"
FROM option_volatility
WHERE asset_code = '$asset_code'""",
        {"x": 12, "y": 17, "w": 6, "h": 4},
        panel_id=5,
    ),
    stat_panel(
        "Всего строк",
        "SELECT COUNT(*) AS total FROM option_volatility",
        {"x": 18, "y": 17, "w": 6, "h": 4},
        panel_id=6,
    ),
]

iv_dashboard = {
    "dashboard": {
        "title": "IV по сериям",
        "tags": ["moex", "options", "iv"],
        "timezone": "browser",
        "panels": iv_panels,
        "templating": {
            "list": [{
                "name": "asset_code",
                "type": "query",
                "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
                "query": "SELECT DISTINCT asset_code FROM option_volatility ORDER BY asset_code",
                "refresh": 1,
                "current": {"text": "SI", "value": "SI"},
            }]
        },
        "time": {"from": "now-7d", "to": "now"},
    },
    "overwrite": True,
}
api("POST", "/api/dashboards/db", iv_dashboard)


# ── Dashboard 3: Кривая волатильности ──

print("\n=== Dashboard: Кривая волатильности ===")

curve_panels = [
    {
        "id": 1,
        "type": "timeseries",
        "title": "Кривая волатильности (все серии)",
        "gridPos": {"x": 0, "y": 0, "w": 24, "h": 11},
        "targets": [sql_target(
            """SELECT strike AS "time", volatility AS "IV",
       optionseries_code AS "metric"
FROM volatility_curve
WHERE asset_code = '$asset_code'
  AND today = (SELECT MAX(today) FROM volatility_curve)
ORDER BY optionseries_code, strike""",
            format_type="table",
        )],
        "fieldConfig": {
            "defaults": {"custom": {"lineWidth": 2, "spanNulls": True}},
            "overrides": [],
        },
        "transformations": [
            {"id": "prepareTimeSeries", "options": {"format": "multi"}},
        ],
        "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
    },
    table_panel(
        "Сводка по сериям",
        """SELECT optionseries_code, series_type, central_strike,
       expiration_date, COUNT(*) AS points,
       MIN(volatility) AS min_iv, MAX(volatility) AS max_iv
FROM volatility_curve
WHERE asset_code = '$asset_code'
  AND today = (SELECT MAX(today) FROM volatility_curve)
GROUP BY optionseries_code, series_type, central_strike, expiration_date
ORDER BY expiration_date""",
        {"x": 0, "y": 11, "w": 24, "h": 8},
        panel_id=2,
    ),
]

curve_dashboard = {
    "dashboard": {
        "title": "Кривая волатильности",
        "tags": ["moex", "options", "volatility_curve"],
        "timezone": "browser",
        "panels": curve_panels,
        "templating": {
            "list": [{
                "name": "asset_code",
                "type": "query",
                "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
                "query": "SELECT DISTINCT asset_code FROM volatility_curve ORDER BY asset_code",
                "refresh": 1,
                "current": {"text": "SI", "value": "SI"},
            }]
        },
        "time": {"from": "now-7d", "to": "now"},
    },
    "overwrite": True,
}
api("POST", "/api/dashboards/db", curve_dashboard)


# ── Dashboard 4: Опционная доска ──

print("\n=== Dashboard: Опционная доска ===")

board_panels = [
    {
        "id": 1,
        "type": "timeseries",
        "title": "Улыбка волатильности",
        "gridPos": {"x": 0, "y": 0, "w": 24, "h": 10},
        "targets": [sql_target(
            """SELECT strike AS "time", volatility AS "IV"
FROM option_std
WHERE asset_code = '$asset_code'
  AND optionseries_code = '$series'
  AND today = (SELECT MAX(today) FROM option_std)
ORDER BY strike""",
            format_type="table",
        )],
        "fieldConfig": {"defaults": {"custom": {"lineWidth": 2}}},
        "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
    },
    {
        "id": 2,
        "type": "timeseries",
        "title": "Delta (Call vs Put)",
        "gridPos": {"x": 0, "y": 10, "w": 12, "h": 8},
        "targets": [sql_target(
            """SELECT strike AS "time", call_delta AS "Call Delta", put_delta AS "Put Delta"
FROM option_std
WHERE asset_code = '$asset_code'
  AND optionseries_code = '$series'
  AND today = (SELECT MAX(today) FROM option_std)
ORDER BY strike""",
            format_type="table",
        )],
        "fieldConfig": {"defaults": {"custom": {"lineWidth": 2}}},
        "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
    },
    {
        "id": 3,
        "type": "timeseries",
        "title": "Gamma (Call vs Put)",
        "gridPos": {"x": 12, "y": 10, "w": 12, "h": 8},
        "targets": [sql_target(
            """SELECT strike AS "time", call_gamma AS "Call Gamma", put_gamma AS "Put Gamma"
FROM option_std
WHERE asset_code = '$asset_code'
  AND optionseries_code = '$series'
  AND today = (SELECT MAX(today) FROM option_std)
ORDER BY strike""",
            format_type="table",
        )],
        "fieldConfig": {"defaults": {"custom": {"lineWidth": 2}}},
        "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
    },
    {
        "id": 4,
        "type": "timeseries",
        "title": "Vega (Call vs Put)",
        "gridPos": {"x": 0, "y": 18, "w": 12, "h": 8},
        "targets": [sql_target(
            """SELECT strike AS "time", call_vega AS "Call Vega", put_vega AS "Put Vega"
FROM option_std
WHERE asset_code = '$asset_code'
  AND optionseries_code = '$series'
  AND today = (SELECT MAX(today) FROM option_std)
ORDER BY strike""",
            format_type="table",
        )],
        "fieldConfig": {"defaults": {"custom": {"lineWidth": 2}}},
        "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
    },
    {
        "id": 5,
        "type": "timeseries",
        "title": "Theta (Call vs Put)",
        "gridPos": {"x": 12, "y": 18, "w": 12, "h": 8},
        "targets": [sql_target(
            """SELECT strike AS "time", call_theta AS "Call Theta", put_theta AS "Put Theta"
FROM option_std
WHERE asset_code = '$asset_code'
  AND optionseries_code = '$series'
  AND today = (SELECT MAX(today) FROM option_std)
ORDER BY strike""",
            format_type="table",
        )],
        "fieldConfig": {"defaults": {"custom": {"lineWidth": 2}}},
        "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
    },
    table_panel(
        "Опционная доска — данные",
        """SELECT strike, volatility, call_offer, call_bid, call_delta, call_gamma,
       call_vega, call_theta, put_offer, put_bid, put_delta, put_gamma,
       put_vega, put_theta
FROM option_std
WHERE asset_code = '$asset_code'
  AND optionseries_code = '$series'
  AND today = (SELECT MAX(today) FROM option_std)
ORDER BY strike""",
        {"x": 0, "y": 26, "w": 24, "h": 8},
        panel_id=6,
    ),
]

board_dashboard = {
    "dashboard": {
        "title": "Опционная доска",
        "tags": ["moex", "options", "optionboard", "greeks"],
        "timezone": "browser",
        "panels": board_panels,
        "templating": {
            "list": [
                {
                    "name": "asset_code",
                    "type": "query",
                    "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
                    "query": "SELECT DISTINCT asset_code FROM option_std ORDER BY asset_code",
                    "refresh": 1,
                    "current": {"text": "SI", "value": "SI"},
                },
                {
                    "name": "series",
                    "type": "query",
                    "datasource": {"type": "grafana-postgresql-datasource", "uid": DS_UID},
                    "query": "SELECT DISTINCT optionseries_code FROM option_std WHERE asset_code='$asset_code' AND today=(SELECT MAX(today) FROM option_std) ORDER BY optionseries_code",
                    "refresh": 2,
                    "current": {},
                },
            ]
        },
        "time": {"from": "now-7d", "to": "now"},
    },
    "overwrite": True,
}
api("POST", "/api/dashboards/db", board_dashboard)


print("\n=== Готово! ===")
print(f"Grafana: http://localhost:3000")
print(f"Логин: admin / admin")
