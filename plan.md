1) На основе файла @Volatility_curve.py подготовь скрипт для загрузки данные в базу данных Postgresql в таблицу с атрибутами: "asset_code","futures_code","optionseries_code","central_strike","series_type","strike","volatility","expiration_date","today". За основу можно взять ранее созданный скрипт @FROM_API_SQL.py
2) Создай файл airflow_volatility_curve.py и напиши в нем DAG для Airflow на основе @airflow_IV.py, используя скрипт передачи данных в базу из файла @Volatility_curve_SQL.py
3) В скрипте @FROM_API_SQL.py необходимо добавить, чтобы в финальную таблицу "option_volatility" добавлен новый атрибут "EXP_STD", который расчитывается из API по формуле: (data_iv["call"][0]['offer'] + data_iv["call"][0]['bid'])/2 + (data_iv['put'][0]['offer'] + data_iv['put'][0]['bid'])/2
4) Также добавь атрубуты:
'CALL_DELTA' - это рассчитывает data_iv["call"][0]['delta'],
'CALL_GAMMA' - это рассчитывает data_iv["call"][0]['gamma'],
'CALL_VEGA' - это рассчитывает data_iv["call"][0]['vega'],
'CALL_THETA' - это рассчитывает data_iv["call"][0]['theta'],
'CALL_RHO' - это рассчитывает data_iv["call"][0]['rho'],
'CALL_INTR_VAL' - это рассчитывает data_iv["call"][0]['intrinsic_value'],
'CALL_T_PRICE' - это рассчитывает data_iv["call"][0]['theorprice'],
'CALL_T_PR_RUB' - это рассчитывает data_iv["call"][0]['theorprice_rub'],
'CALL_NUMTRDS' - это рассчитывает data_iv["call"][0]['numtrades'],
'CALL_TIME_VALUE' - это рассчитывает data_iv["call"][0]['timed_value'],

'PUT_DELTA' - это рассчитывает data_iv["put"][0]['delta'],
'PUT_GAMMA' - это рассчитывает data_iv["put"][0]['gamma'],
'PUT_VEGA' - это рассчитывает data_iv["put"][0]['vega'],
'PUT_THETA' - это рассчитывает data_iv["put"][0]['theta'],
'PUT_RHO' - это рассчитывает data_iv["put"][0]['rho'],
'PUT_INTR_VAL' - это рассчитывает data_iv["put"][0]['intrinsic_value'],
'PUT_T_PRICE' - это рассчитывает data_iv["put"][0]['theorprice'],
'PUT_T_PR_RUB' - это рассчитывает data_iv["put"][0]['theorprice_rub'],
'PUT_NUMTRDS' - это рассчитывает data_iv["put"][0]['numtrades'],
'PUT_TIME_VALUE' - это рассчитывает data_iv["put"][0]['timed_value']

5) На основе скрипта @FROM_API_SQL_PLUS.py создай отдельный файл VOLATILITY_STD.py, в котором поменяй название таблицы для загрузки на "option_std"
6) Создай файл airflow_volatility_STD.py и напиши в нем DAG для Airflow на основе @airflow_volatility_curve.py, используя скрипт передачи данных в базу из файла @VOLATILITY_STD.py