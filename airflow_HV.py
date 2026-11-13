import calendar
import logging
import requests
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.hooks.base import BaseHook

# ============ Параметры DAG ============
DEFAULT_ARGS = {
    'owner': 'vildan-kharisov',
    'retries': 2,
    'retry_delay': timedelta(seconds=600),
    'start_date': datetime(2026, 2, 10),
}

# ============ Параметры загрузки ============
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
HV_LOOKBACK_DAYS = 90
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

def generate_contract_secids(prefix, year_from, year_till):
    """Генерирует все возможные SECID фьючерсов по префиксу и диапазону лет."""
    secids = []
    for year in range(year_from, year_till + 2):
        digit = str(year % 10)
        for mc in MONTH_CODES:
            secids.append(f"{prefix}{mc}{digit}")
    return secids


def approx_expiration(secid, prefix, base_decade):
    """Вычисляет приблизительную дату экспирации из кода SECID.

    Экспирация = 3-й четверг месяца (стандарт MOEX FORTS).
    """
    suffix = secid[len(prefix):]
    month_code = suffix[0]
    year_digit = int(suffix[1])

    month = MONTH_CODE_TO_NUM[month_code]
    year = base_decade + year_digit

    first_weekday = calendar.weekday(year, month, 1)
    first_thursday = 1 + (3 - first_weekday) % 7
    third_thursday = first_thursday + 14

    return datetime(year, month, third_thursday)


def fetch_history_by_secid(secid, date_from, date_till):
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

    return all_rows, columns.split(",")


def compute_hv(closes, window):
    """Рассчитывает последнее значение HV (в %) для списка цен закрытия."""
    if len(closes) < window + 1:
        return None
    arr = np.array(closes, dtype=float)
    log_ret = np.log(arr[1:] / arr[:-1])
    if len(log_ret) < window:
        return None
    rolling_std = np.std(log_ret[-window:], ddof=1)
    hv = rolling_std * np.sqrt(TRADING_DAYS) * 100
    return round(hv, 2)


# ============ Функции задач ============

def get_last_dates_from_db():
    """Получает последнюю дату tradedate по каждому активу из таблицы market_history."""
    connection = BaseHook.get_connection('Postgres')
    conn = psycopg2.connect(
        dbname='postgres_db',
        user=connection.login,
        password=connection.password,
        host=connection.host,
        port=connection.port,
        sslmode='disable',
        connect_timeout=600,
        keepalives_idle=600,
        tcp_user_timeout=600,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            cur.execute(
                "SELECT asset, MAX(tradedate) FROM market_history GROUP BY asset"
            )
            result = {row[0]: row[1] for row in cur.fetchall()}
        conn.commit()
        return result
    finally:
        conn.close()


def fetch_market_data(**kwargs):
    """Задача 1: определить последнюю дату в БД по каждому активу
    и загрузить недостающие данные до текущей даты."""

    today = datetime.now().strftime("%Y-%m-%d")
    date_till = today

    # Получаем последние даты из БД по каждому активу
    last_dates = get_last_dates_from_db()
    logging.info("Последние даты в БД: %s", last_dates)

    all_result_rows = []

    for asset_name, prefix in ASSET_PREFIXES.items():
        logging.info("--- %s (prefix=%s) ---", asset_name, prefix)

        # Определяем начальную дату для загрузки
        last_db_date = last_dates.get(asset_name)
        if last_db_date:
            # Начинаем со следующего дня после последней даты в БД
            dt_from = datetime.combine(last_db_date, datetime.min.time()) + timedelta(days=1)
            date_from = dt_from.strftime("%Y-%m-%d")
            logging.info("  Последняя дата в БД: %s, загружаем с %s", last_db_date, date_from)
        else:
            # Данных нет — загружаем за вчера (первый запуск)
            dt_from = datetime.now() - timedelta(days=1)
            date_from = dt_from.strftime("%Y-%m-%d")
            logging.info("  Данных в БД нет, загружаем с %s", date_from)

        if date_from > date_till:
            logging.info("  Данные уже актуальны, пропускаем.")
            continue

        year_from = dt_from.year
        year_till_num = datetime.now().year
        base_decade = (year_from // 10) * 10

        # Расширенный период для HV
        extended_from = (dt_from - timedelta(days=HV_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

        # 1. Генерируем SECID и вычисляем экспирацию
        secids = generate_contract_secids(prefix, year_from, year_till_num)

        expirations = {}
        for secid in secids:
            expirations[secid] = approx_expiration(secid, prefix, base_decade)

        relevant = {s: e for s, e in expirations.items() if e >= dt_from}

        # 2. Загружаем историю по каждому контракту
        hist_data = {}

        for secid in relevant:
            rows, cols = fetch_history_by_secid(secid, extended_from, date_till)
            if rows:
                hist_data[secid] = rows
                logging.info("  %s: %d строк", secid, len(rows))

        if not hist_data:
            logging.warning("  История пуста для %s", asset_name)
            continue

        # 3. Собираем все торговые даты в новом периоде
        new_trade_dates = set()
        for secid, rows in hist_data.items():
            for row in rows:
                if date_from <= row[0] <= date_till:
                    new_trade_dates.add(row[0])

        for target_date in sorted(new_trade_dates):
            dt_target = datetime.strptime(target_date, "%Y-%m-%d")

            # Ближайший контракт: экспирация >= target_date, минимальная
            best_secid = None
            best_exp = None
            best_row = None

            for secid, rows in hist_data.items():
                exp = expirations.get(secid)
                if exp is None or exp < dt_target:
                    continue
                for row in rows:
                    if row[0] == target_date:
                        if best_exp is None or exp < best_exp:
                            best_secid = secid
                            best_exp = exp
                            best_row = row
                        break

            if best_row is None:
                continue

            # 4. Рассчитываем HV
            closes = []
            for row in hist_data[best_secid]:
                if row[0] <= target_date:
                    close_val = row[4]  # CLOSE
                    if close_val is not None:
                        closes.append(float(close_val))

            hv_values = {}
            for window in HV_WINDOWS:
                hv_values[f"HV_{window}"] = compute_hv(closes, window)

            result = (
                asset_name,
                best_secid,
                best_row[2],   # OPEN
                best_row[3],   # HIGH
                best_row[4],   # LOW
                best_row[5],   # CLOSE -> LAST
                best_row[6],   # SETTLEPRICE
                best_row[7],   # VOLUME -> VOLTODAY
                best_row[8],   # OPENPOSITION
                target_date,
                hv_values.get("HV_10"),
                hv_values.get("HV_20"),
                hv_values.get("HV_30"),
            )
            all_result_rows.append(result)

        logging.info("  Новых дат загружено: %d", len(new_trade_dates))

    logging.info("Всего получено строк: %d", len(all_result_rows))
    kwargs['ti'].xcom_push(key='market_rows', value=all_result_rows)


def load_to_postgres(**kwargs):
    """Задача 2: загрузить данные в PostgreSQL.

    Логика:
    - Если в таблице уже есть записи за эту дату, они обновляются.
    - ID продолжает нумерацию от MAX(id) + 1, или начинается с 1.
    """
    rows = kwargs['ti'].xcom_pull(key='market_rows', task_ids='fetch_market_data')

    if not rows:
        logging.warning("Нет данных для вставки.")
        return

    # Собираем уникальные даты
    trade_dates = list({row[9] for row in rows})

    connection = BaseHook.get_connection('Postgres')
    conn = psycopg2.connect(
        dbname='postgres_db',
        user=connection.login,
        password=connection.password,
        host=connection.host,
        port=connection.port,
        sslmode='disable',
        connect_timeout=600,
        keepalives_idle=600,
        tcp_user_timeout=600,
    )

    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)

            # Удаляем старые записи за загружаемые даты
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
                logging.info("Удалено устаревших строк: %d", existing_count)
            else:
                logging.info("Записей за указанные даты нет -- добавляем новые.")

            # Определяем стартовый id
            cur.execute("SELECT COALESCE(MAX(id), 0) FROM market_history")
            next_id = cur.fetchone()[0] + 1

            # Формируем кортежи для вставки: (id, asset, secid, ...)
            rows_with_id = [
                (next_id + i, *row) for i, row in enumerate(rows)
            ]

            execute_values(cur, INSERT_SQL, rows_with_id)
            logging.info(
                "Вставлено строк: %d (id %d-%d)",
                len(rows_with_id),
                next_id,
                next_id + len(rows_with_id) - 1,
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        logging.error("Ошибка при записи в БД: %s", e)
        raise
    finally:
        conn.close()


# ============ DAG ============

with DAG(
    dag_id='market_history_hv_etl',
    default_args=DEFAULT_ARGS,
    description='Загрузка котировок фьючерсов и HV в PostgreSQL',
    schedule_interval='0 7 * * 1-5',  # Пн-Пт в 07:00
    catchup=False,
    tags=['moex', 'futures', 'hv', 'market_history'],
) as dag:

    start = EmptyOperator(task_id='start')

    fetch_task = PythonOperator(
        task_id='fetch_market_data',
        python_callable=fetch_market_data,
    )

    load_task = PythonOperator(
        task_id='load_to_postgres',
        python_callable=load_to_postgres,
    )

    end = EmptyOperator(task_id='end')

    start >> fetch_task >> load_task >> end
