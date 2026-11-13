import requests
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# Соответствие кода актива → sectype для MOEX ISS API
ASSET_SECTYPES = {
    "SI":   "si",
    "RTS":  "ri",
    "SPYF": "sf",
    "BR":   "br",
    "GOLD": "gd",
    "SILV": "sv",
}

BASE_URL = "https://iss.moex.com/iss/engines/futures/markets/forts/securities.xml"

DISPLAY_COLUMNS = [
    "SECID", "OPEN", "HIGH", "LOW",
    "LAST", "SETTLEPRICE", "VOLTODAY", "OPENPOSITION",
]


def parse_moex_xml(url: str) -> dict[str, pd.DataFrame]:
    """Парсит XML с MOEX ISS и возвращает dict блоков в виде DataFrame."""
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    result = {}
    for block in root.findall("data"):
        rows = [row.attrib for row in block.findall(".//row")]
        if rows:
            result[block.get("id")] = pd.DataFrame(rows)
    return result


def calculate_historical_volatility(
    secid: str, window: int = 20, trading_days: int = 252,
) -> float | None:
    """Рассчитывает историческую волатильность для фьючерса MOEX.

    Загружает историю дневных закрытий через MOEX ISS,
    считает логарифмические доходности и аннуализированную
    скользящую волатильность (последнее значение).

    Parameters:
        secid:        Тикер фьючерса (например, SiH6)
        window:       Окно для расчёта волатильности (в днях)
        trading_days: Количество торговых дней в году для аннуализации

    Returns:
        Последнее значение HV (float) или None если данных недостаточно.
    """
    # Берём запас по дням: window * 2, чтобы хватило торговых дней
    date_from = (datetime.now() - timedelta(days=window * 3)).strftime("%Y-%m-%d")
    date_till = datetime.now().strftime("%Y-%m-%d")

    history_url = (
        f"https://iss.moex.com/iss/history/engines/futures/markets/forts"
        f"/securities/{secid}.json?from={date_from}&till={date_till}"
        f"&iss.meta=off&history.columns=TRADEDATE,CLOSE"
    )

    response = requests.get(history_url, timeout=60)
    response.raise_for_status()
    json_data = response.json()

    rows = json_data.get("history", {}).get("data", [])
    if len(rows) < window + 1:
        return None

    df = pd.DataFrame(rows, columns=["TRADEDATE", "CLOSE"])
    df["CLOSE"] = pd.to_numeric(df["CLOSE"], errors="coerce")
    df = df.dropna(subset=["CLOSE"])

    if len(df) < window + 1:
        return None

    # Логарифмические доходности
    df["log_return"] = np.log(df["CLOSE"] / df["CLOSE"].shift(1))

    # Скользящая волатильность (аннуализированная)
    df["volatility"] = df["log_return"].rolling(window=window).std() * np.sqrt(trading_days)

    last_vol = df["volatility"].iloc[-1]
    if pd.isna(last_vol):
        return None

    return round(last_vol * 100, 2)  # в процентах


def get_nearest_contract(asset_name: str, sectype: str) -> pd.Series | None:
    """Возвращает строку marketdata для ближайшего контракта актива.

    Ближайший контракт определяется по дате LASTTRADEDATE —
    выбирается контракт с самой ближайшей будущей датой экспирации.
    """
    url = f"{BASE_URL}?sectypes={sectype}"
    data = parse_moex_xml(url)

    if "securities" not in data or "marketdata" not in data:
        print(f"  {asset_name}: данные не найдены")
        return None

    sec = data["securities"]
    md = data["marketdata"]

    today = pd.Timestamp.now().normalize()
    sec["LASTTRADEDATE"] = pd.to_datetime(sec["LASTTRADEDATE"])

    # Оставляем только контракты с датой экспирации >= сегодня
    future = sec[sec["LASTTRADEDATE"] >= today]
    if future.empty:
        print(f"  {asset_name}: нет активных контрактов")
        return None

    # Ближайший контракт = минимальная будущая дата экспирации
    nearest = future.sort_values("LASTTRADEDATE").iloc[0]
    ticker = nearest["SECID"]

    # Котировки ближайшего контракта
    quote = md[md["SECID"] == ticker]
    if quote.empty:
        print(f"  {asset_name}: котировки для {ticker} не найдены")
        return None

    row = quote[DISPLAY_COLUMNS].iloc[0].copy()
    row["TRADEDATE"] = quote["TRADEDATE"].iloc[0]

    # Расчёт исторической волатильности
    for window, col_name in [(10, "HV_10"), (20, "HV_20"), (30, "HV_30")]:
        hv = calculate_historical_volatility(ticker, window=window)
        row[col_name] = hv
        print(f"    {col_name} ({ticker}): {hv}")

    return row


def main() -> None:
    rows = []

    for asset_name, sectype in ASSET_SECTYPES.items():
        print(f"--- {asset_name} (sectype={sectype}) ---")
        row = get_nearest_contract(asset_name, sectype)
        if row is not None:
            rows.append(row)

    if not rows:
        print("\nНет данных для отображения.")
        return

    df = pd.DataFrame(rows).reset_index(drop=True)

    # Приводим числовые колонки
    numeric_cols = ["OPEN", "HIGH", "LOW", "LAST", "SETTLEPRICE", "VOLTODAY", "OPENPOSITION"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    print("\n" + "=" * 90)
    print("  Ближайшие фьючерсные контракты (по максимальному открытому интересу)")
    print("=" * 90)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
