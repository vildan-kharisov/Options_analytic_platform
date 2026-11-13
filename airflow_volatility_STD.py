from datetime import datetime, timedelta
import logging
import requests
import psycopg2
from psycopg2.extras import execute_values

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
ASSETS = ["SI", "RTS", "SPYF", "BR", "GOLD", "SILV"]
ASSET_TYPE = "futures"
ROWS = 25
BASE_URL = "https://iss.moex.com/iss/apps/option-calc/v1/assets"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS option_std (
    id              INTEGER PRIMARY KEY,
    asset_code      VARCHAR(10)  NOT NULL,
    futures_code    VARCHAR(20)  NOT NULL,
    optionseries_code VARCHAR(30) NOT NULL,
    central_strike  NUMERIC      NOT NULL,
    series_type     VARCHAR(10)  NOT NULL,
    strike          NUMERIC      NOT NULL,
    volatility      NUMERIC      NOT NULL,
    call_offer      NUMERIC,
    call_bid        NUMERIC,
    call_delta      NUMERIC,
    call_gamma      NUMERIC,
    call_vega       NUMERIC,
    call_theta      NUMERIC,
    call_rho        NUMERIC,
    call_intr_val   NUMERIC,
    call_t_price    NUMERIC,
    call_t_pr_rub   NUMERIC,
    call_numtrds    NUMERIC,
    call_time_value NUMERIC,
    put_offer       NUMERIC,
    put_bid         NUMERIC,
    put_delta       NUMERIC,
    put_gamma       NUMERIC,
    put_vega        NUMERIC,
    put_theta       NUMERIC,
    put_rho         NUMERIC,
    put_intr_val    NUMERIC,
    put_t_price     NUMERIC,
    put_t_pr_rub    NUMERIC,
    put_numtrds     NUMERIC,
    put_time_value  NUMERIC,
    expiration_date DATE         NOT NULL,
    today           DATE         NOT NULL
);
"""

INSERT_SQL = """
INSERT INTO option_std
    (id, asset_code, futures_code, optionseries_code,
     central_strike, series_type, strike, volatility,
     call_offer, call_bid,
     call_delta, call_gamma, call_vega, call_theta, call_rho,
     call_intr_val, call_t_price, call_t_pr_rub, call_numtrds, call_time_value,
     put_offer, put_bid,
     put_delta, put_gamma, put_vega, put_theta, put_rho,
     put_intr_val, put_t_price, put_t_pr_rub, put_numtrds, put_time_value,
     expiration_date, today)
VALUES %s
"""


# ============ Функции задач ============

def fetch_option_std(**kwargs):
    """Задача 1: получить данные optionboard (все страйки) из MOEX API."""

    today = datetime.now().date()
    all_rows = []

    def safe_get(d, key):
        v = d.get(key)
        return v if v is not None else None

    for asset_code in ASSETS:
        logging.info("Загрузка данных по %s", asset_code)
        try:
            url = f"{BASE_URL}/{asset_code}/optionseries?asset_type={ASSET_TYPE}"
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            series_list = response.json()

            for series in series_list:
                optionseries_code = series["optionseries_code"]
                series_asset_type = series["asset_type"]

                url_iv = (
                    f"{BASE_URL}/{series['asset_code']}"
                    f"/optionseries/{optionseries_code}"
                    f"/optionboard?asset_type={series_asset_type}&rows={ROWS}"
                )

                response_iv = requests.get(url_iv, timeout=60)
                response_iv.raise_for_status()
                data_iv = response_iv.json()

                call_list = data_iv.get("call", [])
                put_list = data_iv.get("put", [])
                num_rows = max(len(call_list), len(put_list))

                for i in range(num_rows):
                    call_row = call_list[i] if i < len(call_list) else {}
                    put_row = put_list[i] if i < len(put_list) else {}

                    strike = safe_get(call_row, "strike") or safe_get(put_row, "strike")
                    volatility = safe_get(call_row, "volatility")

                    if strike is None:
                        continue

                    call_offer = safe_get(call_row, "offer")
                    call_bid = safe_get(call_row, "bid")
                    put_offer = safe_get(put_row, "offer")
                    put_bid = safe_get(put_row, "bid")

                    call_delta      = safe_get(call_row, "delta")
                    call_gamma      = safe_get(call_row, "gamma")
                    call_vega       = safe_get(call_row, "vega")
                    call_theta      = safe_get(call_row, "theta")
                    call_rho        = safe_get(call_row, "rho")
                    call_intr_val   = safe_get(call_row, "intrinsic_value")
                    call_t_price    = safe_get(call_row, "theorprice")
                    call_t_pr_rub   = safe_get(call_row, "theorprice_rub")
                    call_numtrds    = safe_get(call_row, "numtrades")
                    call_time_value = safe_get(call_row, "timed_value")

                    put_delta       = safe_get(put_row, "delta")
                    put_gamma       = safe_get(put_row, "gamma")
                    put_vega        = safe_get(put_row, "vega")
                    put_theta       = safe_get(put_row, "theta")
                    put_rho         = safe_get(put_row, "rho")
                    put_intr_val    = safe_get(put_row, "intrinsic_value")
                    put_t_price     = safe_get(put_row, "theorprice")
                    put_t_pr_rub    = safe_get(put_row, "theorprice_rub")
                    put_numtrds     = safe_get(put_row, "numtrades")
                    put_time_value  = safe_get(put_row, "timed_value")

                    row = (
                        series["asset_code"],
                        series["futures_code"],
                        optionseries_code,
                        series["central_strike"],
                        series["series_type"],
                        strike,
                        volatility,
                        call_offer, call_bid,
                        call_delta, call_gamma, call_vega, call_theta, call_rho,
                        call_intr_val, call_t_price, call_t_pr_rub,
                        call_numtrds, call_time_value,
                        put_offer, put_bid,
                        put_delta, put_gamma, put_vega, put_theta, put_rho,
                        put_intr_val, put_t_price, put_t_pr_rub,
                        put_numtrds, put_time_value,
                        series["expiration_date"],
                        str(today),
                    )
                    all_rows.append(row)

                logging.info(
                    "  %s  %s  %s  strike=%s  type=%s  rows=%d",
                    series["asset_code"],
                    series["futures_code"],
                    optionseries_code,
                    series["central_strike"],
                    series["series_type"],
                    num_rows,
                )

        except requests.RequestException as e:
            logging.error("Ошибка API для %s: %s", asset_code, e)

    logging.info("Всего получено строк: %d", len(all_rows))
    kwargs['ti'].xcom_push(key='option_std_rows', value=all_rows)


def load_to_postgres_std(**kwargs):
    """Задача 2: загрузить данные в PostgreSQL (таблица option_std).

    Логика:
    - Если в таблице уже есть записи с today = текущая дата,
      они удаляются и заменяются новыми (обновление за сегодня).
    - Если записей за текущую дату нет, новые строки просто добавляются.
    - ID продолжает нумерацию от MAX(id) + 1, или начинается с 1.
    """

    rows = kwargs['ti'].xcom_pull(
        key='option_std_rows', task_ids='fetch_option_std'
    )

    if not rows:
        logging.warning("Нет данных для вставки.")
        return

    today = datetime.now().date()

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
                "SELECT COUNT(*) FROM option_std WHERE today = %s",
                (today,),
            )
            existing_count = cur.fetchone()[0]

            if existing_count > 0:
                cur.execute(
                    "DELETE FROM option_std WHERE today = %s",
                    (today,),
                )
                logging.info(
                    "Удалено устаревших строк за %s: %d", today, existing_count
                )
            else:
                logging.info("Записей за %s нет — добавляем новые.", today)

            cur.execute("SELECT COALESCE(MAX(id), 0) FROM option_std")
            next_id = cur.fetchone()[0] + 1

            rows_with_id = [
                (next_id + i, *row) for i, row in enumerate(rows)
            ]

            execute_values(cur, INSERT_SQL, rows_with_id)
            logging.info(
                "Вставлено строк: %d (id %d\u2013%d)",
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
    dag_id='option_std_etl',
    default_args=DEFAULT_ARGS,
    description='Загрузка опционной доски (страйки + греки) MOEX в PostgreSQL',
    schedule_interval='0 10-18 * * 1-5',
    catchup=False,
    tags=['moex', 'options', 'optionboard', 'greeks'],
) as dag:

    start = EmptyOperator(task_id='start')

    fetch_task = PythonOperator(
        task_id='fetch_option_std',
        python_callable=fetch_option_std,
    )

    load_task = PythonOperator(
        task_id='load_to_postgres_std',
        python_callable=load_to_postgres_std,
    )

    end = EmptyOperator(task_id='end')

    start >> fetch_task >> load_task >> end
