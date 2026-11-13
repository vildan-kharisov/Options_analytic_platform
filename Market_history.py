import calendar
import requests
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta


# ============ Настройки подключения к PostgreSQL ============
DB_CONFIG = {
    "host": "localhost",
    "port": 7777,
    "dbname": "postgres",
    "user": "postgres",
    "password": "mysecretpassword",
}

# ============ Параметры ============
DATE_FROM = "2020-01-03"
DATE_TILL = "2026-02-11"

# Префиксы SECID на MOEX FORTS для каждого актива
ASSET_PREFIXES = {
    "SI":   "Si",
    "RTS":  "RI",
    "SPYF": "SF",
    "BR":   "BR",
    "GOLD": "GD",
    "SILV": "SV",
}

MONTH_CODE_TO_NUM = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}
MONTH_CODES = list(MONTH_CODE_TO_NUM.keys())

HISTORY_URL = "https://iss.moex.com/iss/history/engines/futures/markets/forts/securities"

HV_WINDOWS = [10, 20, 30]
HV_LOOKBACK_DAYS = 90   # календарных дней до DATE_FROM для расчёта HV
TRADING_DAYS = 252

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS market_history (
    id             INTEGER PRIMARY KEY,
    asset          VARCHAR(10)  NOT NULL,
    secid          VARCHAR(20)  NOT NULL,
    open           NUMERIC,
    high           NUMERIC,
    low            NUMERIC,
    last           NUMERIC,
    settleprice    NUMERIC,
    voltoday       NUMERIC,
    openposition   NUMERIC,
    tradedate      DATE         NOT NULL,
    hv_10          NUMERIC,
    hv_20          NUMERIC,
    hv_30          NUMERIC
);
"""

INSERT_SQL = """
INSERT INTO market_history
    (id, asset, secid, open, high, low, last, settleprice,
     voltoday, openposition, tradedate, hv_10, hv_20, hv_30)
VALUES %s
"""


# ============ Вспомогательные функции ============

def generate_contract_secids(prefix: str, year_from: int, year_till: int) -> list[str]:
    """Генерирует все возможные SECID фьючерсов по префиксу и диапазону лет.

    Перебирает все комбинации: prefix + месяц (F..Z) + цифра года.
    Несуществующие контракты просто вернут пустой ответ API.
    """
    secids = []
    for year in range(year_from, year_till + 2):
        digit = str(year % 10)
        for mc in MONTH_CODES:
            secids.append(f"{prefix}{mc}{digit}")
    return secids


def approx_expiration(secid: str, prefix: str, base_decade: int) -> pd.Timestamp:
    """Вычисляет приблизительную дату экспирации из кода SECID.

    SECID формат: prefix + месяц_код + цифра_года.
    Экспирация = 3-й четверг месяца (стандарт MOEX FORTS).
    """
    suffix = secid[len(prefix):]       # например "H6" из "SiH6"
    month_code = suffix[0]
    year_digit = int(suffix[1])

    month = MONTH_CODE_TO_NUM[month_code]
    year = base_decade + year_digit

    # 3-й четверг месяца: находим день недели 1-го числа,
    # вычисляем первый четверг, затем +14 дней
    first_weekday = calendar.weekday(year, month, 1)  # 0=Пн, 3=Чт
    first_thursday = 1 + (3 - first_weekday) % 7
    third_thursday = first_thursday + 14

    return pd.Timestamp(year, month, third_thursday)


def fetch_history_by_secid(secid: str, date_from: str, date_till: str) -> pd.DataFrame:
    """Загружает историю торгов для конкретного SECID за период."""
    columns = "TRADEDATE,SECID,OPEN,HIGH,LOW,CLOSE,SETTLEPRICE,VOLUME,OPENPOSITION"
    all_rows = []
    start = 0

    while True:
        url = (
            f"{HISTORY_URL}/{secid}.json"
            f"?from={date_from}&till={date_till}"
            f"&start={start}&iss.meta=off"
            f"&history.columns={columns}"
        )
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        data = response.json()
        rows = data.get("history", {}).get("data", [])
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < 100:
            break
        start += len(rows)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows, columns=columns.split(","))
    return df


def compute_hv_series(closes: pd.Series, window: int) -> pd.Series:
    """Рассчитывает скользящую историческую волатильность (в %)."""
    log_ret = np.log(closes / closes.shift(1))
    hv = log_ret.rolling(window=window).std() * np.sqrt(TRADING_DAYS) * 100
    return hv.round(2)


# ============ Основная логика ============

def build_history_table(date_from: str, date_till: str) -> pd.DataFrame:
    """Собирает таблицу котировок ближайших контрактов за период.

    Для каждой торговой даты ближайший контракт определяется по LSTTRADE —
    выбирается контракт с минимальной датой экспирации >= дата торгов.
    """
    dt_from = pd.Timestamp(date_from)
    dt_till = pd.Timestamp(date_till)
    year_from = dt_from.year
    year_till = dt_till.year

    # Расширенный период для расчёта HV
    extended_from = (dt_from - timedelta(days=HV_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    all_result_rows = []

    for asset_name, prefix in ASSET_PREFIXES.items():
        print(f"\n--- {asset_name} (prefix={prefix}) ---")

        # 1. Генерируем все возможные SECID и вычисляем дату экспирации
        base_decade = (year_from // 10) * 10  # 2020 для 2020-2029
        secids = generate_contract_secids(prefix, year_from, year_till)

        expirations: dict[str, pd.Timestamp] = {}
        for secid in secids:
            expirations[secid] = approx_expiration(secid, prefix, base_decade)

        # Оставляем только контракты с экспирацией >= начало периода
        relevant = {s: e for s, e in expirations.items() if e >= dt_from}
        print(f"  Контрактов для проверки: {len(relevant)}")

        # 2. Загружаем историю по каждому релевантному контракту
        hist_frames = []
        for secid in relevant:
            df_sec = fetch_history_by_secid(secid, extended_from, date_till)
            if not df_sec.empty:
                hist_frames.append(df_sec)
                print(f"    {secid} (до {expirations[secid].strftime('%Y-%m-%d')}): {len(df_sec)} строк")

        if not hist_frames:
            print(f"  История пуста")
            continue

        hist = pd.concat(hist_frames, ignore_index=True)

        # Приводим типы
        numeric_cols = ["OPEN", "HIGH", "LOW", "CLOSE", "SETTLEPRICE", "VOLUME", "OPENPOSITION"]
        for col in numeric_cols:
            hist[col] = pd.to_numeric(hist[col], errors="coerce")
        hist["TRADEDATE"] = pd.to_datetime(hist["TRADEDATE"])

        # Добавляем LSTTRADE из спецификации к каждой строке
        hist["LSTTRADE"] = hist["SECID"].map(expirations)

        # 3. Торговые даты в запрошенном периоде
        trade_dates = sorted(hist[
            (hist["TRADEDATE"] >= dt_from) & (hist["TRADEDATE"] <= dt_till)
        ]["TRADEDATE"].unique())

        prev_nearest = None
        for trade_date in trade_dates:
            # Все контракты, которые торговались в эту дату
            day_data = hist[hist["TRADEDATE"] == trade_date].copy()

            # Ближайший контракт: LSTTRADE >= trade_date, минимальный LSTTRADE
            candidates = day_data[day_data["LSTTRADE"] >= trade_date]
            if candidates.empty:
                continue

            nearest = candidates.sort_values("LSTTRADE").iloc[0]
            nearest_secid = nearest["SECID"]

            result = {
                "ASSET": asset_name,
                "SECID": nearest_secid,
                "OPEN": nearest["OPEN"],
                "HIGH": nearest["HIGH"],
                "LOW": nearest["LOW"],
                "LAST": nearest["CLOSE"],
                "SETTLEPRICE": nearest["SETTLEPRICE"],
                "VOLTODAY": nearest["VOLUME"],
                "OPENPOSITION": nearest["OPENPOSITION"],
                "TRADEDATE": trade_date.strftime("%Y-%m-%d"),
            }

            # Рассчитываем HV на основе истории ближайшего контракта до trade_date
            contract_hist = hist[
                (hist["SECID"] == nearest_secid) & (hist["TRADEDATE"] <= trade_date)
            ].sort_values("TRADEDATE")

            for window in HV_WINDOWS:
                col_name = f"HV_{window}"
                if len(contract_hist) >= window + 1:
                    hv_series = compute_hv_series(contract_hist["CLOSE"], window)
                    result[col_name] = hv_series.iloc[-1]
                else:
                    result[col_name] = None

            all_result_rows.append(result)

            if nearest_secid != prev_nearest:
                if prev_nearest is not None:
                    print(f"  >> Смена контракта: {prev_nearest} -> {nearest_secid} ({trade_date.strftime('%Y-%m-%d')})")
                prev_nearest = nearest_secid

        print(f"  Итого: {len(trade_dates)} торговых дней")

    if not all_result_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_result_rows)
    return df


# ============ Загрузка в БД ============

def load_to_db(df: pd.DataFrame) -> None:
    """Загружает DataFrame в таблицу market_history PostgreSQL.

    Логика:
    - Если в таблице уже есть записи с tradedate из загружаемого периода,
      они удаляются и заменяются новыми.
    - ID продолжает нумерацию от MAX(id) + 1, или начинается с 1.
    """
    if df.empty:
        print("\n>>> Нет данных для вставки.")
        return

    trade_dates = [
        pd.Timestamp(d).date() for d in df["TRADEDATE"].unique()
    ]

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)

            cur.execute(
                "SELECT COUNT(*) FROM market_history WHERE tradedate = ANY(%s::date[])",
                (trade_dates,),
            )
            existing_count = cur.fetchone()[0]

            if existing_count > 0:
                cur.execute(
                    "DELETE FROM market_history WHERE tradedate = ANY(%s::date[])",
                    (trade_dates,),
                )
                print(f"\n>>> Удалено устаревших строк: {existing_count}")
            else:
                print(f"\n>>> Записей за указанные даты нет — добавляем новые.")

            cur.execute("SELECT COALESCE(MAX(id), 0) FROM market_history")
            next_id = cur.fetchone()[0] + 1

            rows = []
            for i, (_, row) in enumerate(df.iterrows()):
                tradedate = pd.Timestamp(row["TRADEDATE"]).date()
                rows.append((
                    next_id + i,
                    row["ASSET"],
                    row["SECID"],
                    row["OPEN"],
                    row["HIGH"],
                    row["LOW"],
                    row["LAST"],
                    row["SETTLEPRICE"],
                    row["VOLTODAY"],
                    row["OPENPOSITION"],
                    tradedate,
                    row.get("HV_10"),
                    row.get("HV_20"),
                    row.get("HV_30"),
                ))

            execute_values(cur, INSERT_SQL, rows)
            print(
                f">>> Вставлено строк: {len(rows)} "
                f"(id {next_id}–{next_id + len(rows) - 1})"
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"\n>>> Ошибка при записи в БД: {e}")
        raise
    finally:
        conn.close()


# ============ Запуск ============

def main() -> None:
    print(f"Период: {DATE_FROM} — {DATE_TILL}\n")

    df = build_history_table(DATE_FROM, DATE_TILL)

    if df.empty:
        print("\nНет данных для отображения.")
        return

    print("\n" + "=" * 120)
    print(f"  Ближайшие фьючерсные контракты за период {DATE_FROM} — {DATE_TILL}")
    print("=" * 120)
    print(df.to_string(index=False))
    print(f"\nВсего строк: {len(df)}")

    load_to_db(df)
    print("Готово.")


if __name__ == "__main__":
    main()
