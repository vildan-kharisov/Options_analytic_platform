Готово — подготовил практический SQL-пакет в папке d:\Algo\Options\sql:
sql/portfolio_schema.sql — DDL прикладных таблиц Portfolio Lab
(portfolio, portfolio_leg, portfolio_snapshot, scenario_run + индексы + триггеры updated_at)
sql/views_market_inputs.sql — представления для нормализации ETL-данных
(включая маппинг market_history.asset -> asset_code, latest-срезы, v_iv_next_month, v_hv_iv_daily)
sql/queries_portfolio.sql — готовые рабочие запросы для API
(spot, valuation с Greeks из option_std, payoff grid, insert snapshot, insert scenario)
Как применить (PowerShell)
psql -h 192.168.1.100 -p 5430 -U <POSTGRES_USER> -d <POSTGRES_DB> -f "d:\Algo\Options\sql\portfolio_schema.sql"psql -h 192.168.1.100 -p 5430 -U <POSTGRES_USER> -d <POSTGRES_DB> -f "d:\Algo\Options\sql\views_market_inputs.sql"
queries_portfolio.sql — это библиотека SQL для использования из Python API (его не нужно “выполнять целиком”