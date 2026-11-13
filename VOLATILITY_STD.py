import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

# ============ Настройки подключения к PostgreSQL ============
DB_CONFIG = {
    "host": "localhost",
    "port": 7777,
    "dbname": "postgres",
    "user": "postgres",
    "password": "mysecretpassword",
}

# ============ Параметры загрузки ============
ASSETS = ["SI", "RTS", "SPYF", "BR", "GOLD", "SILV"]
ASSET_TYPE = "futures"
ROWS = 25 # количество строк от центрального страйка (0 = только центральный)

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


def fetch_volatility(asset_code: str, asset_type: str) -> list[tuple]:
    """Получает данные по волатильности из MOEX API для указанного актива."""

    today = datetime.now().date()
    url = f"{BASE_URL}/{asset_code}/optionseries?asset_type={asset_type}"

    response = requests.get(url)
    response.raise_for_status()
    series_list = response.json()

    def safe_get(d, key):
        v = d.get(key)
        return v if v is not None else None

    rows: list[tuple] = []

    for series in series_list:
        optionseries_code = series["optionseries_code"]
        series_asset_type = series["asset_type"]

        url_iv = (
            f"{BASE_URL}/{series['asset_code']}"
            f"/optionseries/{optionseries_code}"
            f"/optionboard?asset_type={series_asset_type}&rows={ROWS}"
        )

        response_iv = requests.get(url_iv)
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
                call_intr_val, call_t_price, call_t_pr_rub, call_numtrds, call_time_value,
                put_offer, put_bid,
                put_delta, put_gamma, put_vega, put_theta, put_rho,
                put_intr_val, put_t_price, put_t_pr_rub, put_numtrds, put_time_value,
                series["expiration_date"],
                today,
            )
            rows.append(row)

        print(
            f"  {series['asset_code']:<5s} "
            f"{series['futures_code']:<10s} "
            f"{optionseries_code:<20s} "
            f"{series['central_strike']:<10} "
            f"{series['series_type']:<5s} "
            f"rows={num_rows:<5} "
            f"{series['expiration_date']:<15} "
            f"{today}"
        )

    return rows


def load_to_db(rows: list[tuple]) -> None:
    """Создаёт таблицу (если не существует) и вставляет строки в PostgreSQL.

    Логика:
    - Если в таблице уже есть записи с today = текущая дата,
      они удаляются и заменяются новыми (обновление за сегодня).
    - Если записей за текущую дату нет, новые строки просто добавляются.
    """

    today = datetime.now().date()
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)

            if not rows:
                print("\n>>> Нет данных для вставки.")
                conn.commit()
                return

            # Проверяем, есть ли уже записи за сегодня
            cur.execute(
                "SELECT COUNT(*) FROM option_std WHERE today = %s",
                (today,),
            )
            existing_count = cur.fetchone()[0]

            if existing_count > 0:
                # Удаляем старые записи за сегодня и вставляем свежие
                cur.execute(
                    "DELETE FROM option_std WHERE today = %s",
                    (today,),
                )
                print(f"\n>>> Удалено устаревших строк за {today}: {existing_count}")
            else:
                print(f"\n>>> Записей за {today} нет — добавляем новые.")

            # Определяем стартовый id: MAX(id) + 1, или 1 если таблица пуста
            cur.execute("SELECT COALESCE(MAX(id), 0) FROM option_std")
            next_id = cur.fetchone()[0] + 1

            # Добавляем id к каждой строке
            rows_with_id = [
                (next_id + i, *row) for i, row in enumerate(rows)
            ]

            execute_values(cur, INSERT_SQL, rows_with_id)
            print(
                f">>> Вставлено строк: {len(rows_with_id)} "
                f"(id {next_id}\u2013{next_id + len(rows_with_id) - 1})"
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"\n>>> Ошибка при записи в БД: {e}")
        raise
    finally:
        conn.close()


def main() -> None:
    all_rows: list[tuple] = []

    for asset in ASSETS:
        print(f"\n--- Загрузка данных по {asset} ---")
        try:
            rows = fetch_volatility(asset, ASSET_TYPE)
            all_rows.extend(rows)
        except requests.RequestException as e:
            print(f"  Ошибка API для {asset}: {e}")

    print(f"\nВсего получено строк: {len(all_rows)}")
    load_to_db(all_rows)
    print("Готово.")


if __name__ == "__main__":
    main()
