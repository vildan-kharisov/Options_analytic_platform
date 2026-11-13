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
BASE_URL = "https://iss.moex.com/iss/apps/option-calc/v1/assets"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS option_volatility (
    id              INTEGER PRIMARY KEY,
    asset_code      VARCHAR(10)  NOT NULL,
    futures_code    VARCHAR(20)  NOT NULL,
    optionseries_code VARCHAR(30) NOT NULL,
    central_strike  NUMERIC      NOT NULL,
    series_type     VARCHAR(10)  NOT NULL,
    volatility      NUMERIC      NOT NULL,
    expiration_date DATE         NOT NULL,
    today           DATE         NOT NULL
);
"""

INSERT_SQL = """
INSERT INTO option_volatility
    (id, asset_code, futures_code, optionseries_code,
     central_strike, series_type, volatility,
     expiration_date, today)
VALUES %s
"""


# ============ Функции задач ============

def fetch_volatility(**kwargs):
    """Задача 1: получить данные по волатильности из MOEX API."""

    today = datetime.now().date()
    all_rows = []

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
                    f"/optionboard?asset_type={series_asset_type}&rows=0"
                )

                response_iv = requests.get(url_iv, timeout=60)
                response_iv.raise_for_status()
                data_iv = response_iv.json()

                volatility = data_iv["call"][0]["volatility"]

                row = (
                    series["asset_code"],
                    series["futures_code"],
                    optionseries_code,
                    series["central_strike"],
                    series["series_type"],
                    volatility,
                    series["expiration_date"],
                    str(today),
                )
                all_rows.append(row)
                logging.info(
                    "  %s  %s  %s  strike=%s  type=%s  vol=%s  exp=%s",
                    series["asset_code"],
                    series["futures_code"],
                    optionseries_code,
                    series["central_strike"],
                    series["series_type"],
                    volatility,
                    series["expiration_date"],
                )

        except requests.RequestException as e:
            logging.error("Ошибка API для %s: %s", asset_code, e)

    logging.info("Всего получено строк: %d", len(all_rows))

    # Передаём данные в следующую задачу через XCom
    kwargs['ti'].xcom_push(key='volatility_rows', value=all_rows)


def load_to_postgres(**kwargs):
    """Задача 2: загрузить данные в PostgreSQL.

    Логика:
    - Если в таблице уже есть записи с today = текущая дата,
      они удаляются и заменяются новыми (обновление за сегодня).
    - Если записей за текущую дату нет, новые строки просто добавляются.
    - ID продолжает нумерацию от MAX(id) + 1, или начинается с 1.
    """

    # Получаем данные из предыдущей задачи через XCom
    rows = kwargs['ti'].xcom_pull(key='volatility_rows', task_ids='fetch_volatility')

    if not rows:
        logging.warning("Нет данных для вставки.")
        return

    today = datetime.now().date()

    # Подключение через Airflow Connection 'Postgres'
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

            # Проверяем, есть ли уже записи за сегодня
            cur.execute(
                "SELECT COUNT(*) FROM option_volatility WHERE today = %s",
                (today,),
            )
            existing_count = cur.fetchone()[0]

            if existing_count > 0:
                cur.execute(
                    "DELETE FROM option_volatility WHERE today = %s",
                    (today,),
                )
                logging.info("Удалено устаревших строк за %s: %d", today, existing_count)
            else:
                logging.info("Записей за %s нет — добавляем новые.", today)

            # Определяем стартовый id
            cur.execute("SELECT COALESCE(MAX(id), 0) FROM option_volatility")
            next_id = cur.fetchone()[0] + 1

            # Добавляем id к каждой строке
            rows_with_id = [
                (next_id + i, *row) for i, row in enumerate(rows)
            ]

            execute_values(cur, INSERT_SQL, rows_with_id)
            logging.info(
                "Вставлено строк: %d (id %d–%d)",
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
    dag_id='option_volatility_etl',
    default_args=DEFAULT_ARGS,
    description='Загрузка волатильности опционов MOEX в PostgreSQL',
    schedule_interval='0 10-18 * * 1-5',  # Пн–Пт каждый час с 10:00 до 18:00
    catchup=False,
    tags=['moex', 'options', 'volatility'],
) as dag:

    start = EmptyOperator(task_id='start')

    fetch_task = PythonOperator(
        task_id='fetch_volatility',
        python_callable=fetch_volatility,
    )

    load_task = PythonOperator(
        task_id='load_to_postgres',
        python_callable=load_to_postgres,
    )

    end = EmptyOperator(task_id='end')

    start >> fetch_task >> load_task >> end
