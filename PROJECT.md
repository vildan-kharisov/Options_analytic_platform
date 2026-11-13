"OPTIONS" - это дашборд на основе Apache ECharts с источником базы данных PostgreSQL и API опционого калькулятора. Основна цель  - помочь трейдеру в принятии торговых решений по опционам и моделирование опционных стратегий. Самое важное - это понимание historical volatility,  implied volatility, volatility curve (volatility smile) в разрезе различных базовых активов и опционных серий. Также в функционале чтобы было предусмотерено построение и моделирование опционного портфеля через API опционного калькулятора.

Архитектура:
1) Flask API (echarts_api.py) — отдаёт данные из PostgreSQL как JSON
2) HTML + ECharts (echarts_dashboard.html) — рендерит интерактивные графики
3) API опционного калькулятора: "https://iss.moex.com/iss/apps/option-calc/v1/docs"
4) База данных: .env.POSTGRES_DB, host: 192.168.1.100, port: 5430,  user: .env.POSTGRES_USER, password: .env.POSTGRES_PASSWORD
Таблицы, которые можно использовать в базе данных:
    public.market_history;
    public.option_volatility;
    public.volatility_curve;
    public.option_volatility_plus;
    public.option_std;
5) Для ввода данных и моделирования опционного портфеля на основе API, предложи свои варианты.

### Рекомендуемая архитектура
Сервер 192.168.1.100
Docker Airflow (только ETL/DAG)
PostgreSQL (единый источник данных)
Никаких UI/Flask/ECharts для разработки
Локальная машина
echarts_api.py + echarts_dashboard.html
разработка SQL/API/UI
подключение к удаленной БД на сервере

3 вкладки:
1. SI. Здесь располагаются все графики и основная информация по базовому активу "SI"
2. RTS. Здесь располагаются все графики и основная информация по базовому активу "RTS"
3. GOLD. Здесь располагаются все графики и основная информация по базовому активу "GOLD"
4. BRENT. Здесь располагаются все графики и основная информация по базовому активу "BRENT"

На каждой вкладке должны быть графики:
- График "OHLC", построенный по историческим ценам базового актива. График масштабируется и должен иметь возможность рисования горизонтальных и вертикальных линий и возможностью их двигать и удалять. Данные можно взять из БД в таблице public.market_history, атрибуты для цен: open,high,low,last. На график также нанеси линии стандартного отклонения, данные по отклоениям взяты из public.option_volatility_plus, пример скрипта с отклонениями с инструментом 'RTS':
"
SELECT hv.tradedate,hv.asset,hv.secid, hv.LAST,iv.exp_std,
hv.LAST + iv.exp_std up,
hv.LAST -iv.exp_std down
FROM public.market_history hv
LEFT JOIN public.option_volatility_plus iv
ON  hv.asset = iv.asset_code 
AND upper(hv.secid) = iv.futures_code
AND hv.tradedate = Iv.today 
AND iv.series_type = 'Q'
WHERE hv.asset = 'RTS'
ORDER BY hv.tradedate ;
"

- График "HV 10/20/30/IV", построенный по данным исторической волатильности актива. График масштабируется и должен иметь возможность рисования горизонтальных и вертикальных линий и возможностью их двигать и удалять. Данные можно взять из БД в таблице public.market_history. Атриубуты исторической волатильности: hv_10,hv_20,hv_30. Для IV(implied Volatility) можно взять данные из public.option_volatility, она должна рассчитываться по данным волатильности инструмента, у которого экспириция в следующем месяце. Например, если сегодня февраль 2026 года, то необходимо взять контракт, который имеет дату эсприрации в следующем месяце то есть в марте 2026 года и тип серии было 'Q'или'M'. На языке SQL это писалось бы: "where series_type in ('Q','M') AND extract(MONTH FROM today)+1 = extract(MONTH FROM expiration_date)".

- График "Кривой волатильности" (Volatility Curve). Расчитывается сама кривая волатильности также по контракту, у которого эспирация в следующем месяце, а также стандартное отлонение этой кривой взвешенной. 
Для примера: "http://localhost:12345/dashboard/2-options?tab=4-si". График "SI_STD_NORMAL"
Вот скрит для этого графика:
"
--Отлонения с нормализацией по центральному страйку
SELECT futures_code,optionseries_code,series_type,delta_type,
CASE
	WHEN delta_type = 'put_5' THEN 0
	WHEN delta_type = 'put_10' THEN 1
	WHEN delta_type = 'put_25' THEN 2
	WHEN delta_type = 'center' THEN 3
	WHEN delta_type = 'call_25' THEN 4
	WHEN delta_type = 'call_10' THEN 5
	WHEN delta_type = 'call_5' THEN 6
END num,
max(last_val) current_value,
round(sum(delta_ratio * weights)/sum(weights),2) WMA,
round(sum(std * weights)/sum(weights),2) STD_WMA,
round(sum(delta_ratio * weights)/sum(weights) *(1+sum(std * weights)/sum(weights)),2) up,
round(sum(delta_ratio * weights)/sum(weights) *(1-sum(std * weights)/sum(weights)),2) down
FROM 
(SELECT futures_code,optionseries_code,series_type,volatility,delta_type,delta_ratio,weights,
coalesce(stddev(delta_ratio) over(PARTITION BY delta_type ORDER BY today ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),0)std,
LAST_VALUE(delta_ratio) OVER (PARTITION BY delta_type) last_val,
expiration_date,today
from
(SELECT futures_code,optionseries_code,series_type,volatility,delta_type,
round(volatility/max(CASE 
	WHEN delta_type = 'center' THEN volatility
	ELSE 0
END ) OVER (PARTITION BY today),2)delta_ratio,
ROW_NUMBER()  over(PARTITION BY delta_type ORDER BY today ASC)weights,
expiration_date,today
from
(SELECT futures_code,optionseries_code,series_type,central_strike,strike,volatility,call_delta,put_delta,
CASE 
	WHEN min_call_25 = call_25 THEN 'call_25'
	WHEN min_call_10 = call_10 THEN 'call_10'
	WHEN min_call_5 = call_5 THEN 'call_5'
	WHEN min_put_25 = put_25 THEN 'put_25'
	WHEN min_put_10 = put_10 THEN 'put_10'
	WHEN min_put_5 = put_5 THEN 'put_5'
	WHEN central_strike = strike THEN 'center'
END delta_type,
expiration_date,today
from
(SELECT futures_code,optionseries_code,series_type,central_strike,strike,volatility,call_delta,put_delta,expiration_date,today,
abs(0.25-call_delta) call_25,
min(abs(0.25-call_delta)) over(partition BY today) min_call_25,
abs(0.10-call_delta) call_10,
min(abs(0.10-call_delta)) over(partition BY today) min_call_10,
abs(0.05-call_delta) call_5,
min(abs(0.05-call_delta)) over(partition BY today) min_call_5,
abs(0.25 + put_delta) put_25,
min(abs(0.25 + put_delta)) over(partition BY today) min_put_25,
abs(0.10 + put_delta) put_10,
min(abs(0.10 + put_delta)) over(partition BY today) min_put_10,
abs(0.05 + put_delta) put_5,
min(abs(0.05 + put_delta)) over(partition BY today) min_put_5
FROM public.option_std
WHERE 1=1
AND series_type in ('Q','M')
AND extract(MONTH FROM today)+1 = extract(MONTH FROM expiration_date)
AND asset_code = 'RTS'
)
WHERE min_call_25 = call_25
or min_call_10 = call_10
OR min_call_5 = call_5
OR min_put_25 = put_25
or min_put_10 = put_10
OR min_put_5 = put_5
OR central_strike = strike)
WHERE (today - 365) <= today
))
GROUP by
futures_code,optionseries_code,series_type,delta_type,
CASE
	WHEN delta_type = 'put_5' THEN 0
	WHEN delta_type = 'put_10' THEN 1
	WHEN delta_type = 'put_25' THEN 2
	WHEN delta_type = 'center' THEN 3
	WHEN delta_type = 'call_25' THEN 4
	WHEN delta_type = 'call_10' THEN 5
	WHEN delta_type = 'call_5' THEN 6
END 
ORDER BY num;
"
- График "График временной структуры опциона". Отображает график с волатильностью по центральным страйкам одного и того же базового актива, но с разным периодом погашения. Для примера: "http://localhost:12345/dashboard/2-options?tab=4-si". График "SI_Time_Structure". Скрипт, используемый для построения по инструменту "SI":
"--Временная структура
SELECT *
FROM public.option_volatility v
WHERE asset_code = 'SI'
AND today = (SELECT max(today) FROM public.option_volatility t WHERE t.asset_code = v.asset_code )
ORDER BY expiration_date
;
"
- График "Улыбка волатильности по сериям". На графике отображается кривая волатильности по выбранным сериям, серия быть одна или несколько, по умолчанию одна, но с возможностью добавить остальные и чтобы все были отображены на одном графике. Для примера график "Улыбка волатильности" на вкладке "Опционная доска" в "echarts_dashboard.html", но с функционалом, который описал в этом пункте.

- Четыре связанных графика "Delta", "Gamma", "Vega", "Theta". Графики связаны через один селектор по выбранным сериям по данному активу в этой вкладке.

- График "Открытые позиции в контрактах". Показывает количество открытых позиций на разных страйках опционной серии. Например "https://www.moex.com/ru/derivatives/optionsdeskstat.aspx?code=RTS-3.26M190326CA&sid=1#SP".  Или в табличном варианте на сайте "https://www.moex.com/ru/derivatives/optionsdesk.aspx?code=RTS-3.26&sid=1&sby=1&c4=on&submit=submit#19032026". Предоложи варианты где можно взять источник для зарузки этих данных.

## Дополнительные рекомендации по визуализации

### Что добавить в графики (самое полезное)
1) IV Rank / IV Percentile (252d)  
Для каждого актива и серии: где текущая IV находится относительно своего годового диапазона. Это практичный сигнал для принятия решения по покупке/продаже волатильности.

2) Spread IV - HV (10/20/30) + Z-score  
Отдельный график переоценки/недооценки волатильности: `IV_next_month - HV_20` и его стандартизация.

3) Skew индикатор  
Линия вида `IV(put_25Δ) - IV(call_25Δ)` по времени. Показывает перекос улыбки и изменение страховой премии в put-опционах.

4) Term Structure Heatmap  
Тепловая карта: ось X — дата, ось Y — срок до экспирации (DTE), цвет — IV. Позволяет видеть contango/backwardation по волатильности.

5) Smile evolution (анимация/слайдер дат)  
Улыбка волатильности с прокруткой по датам, чтобы визуально отслеживать смену рыночного режима.

6) PnL-сценарии портфеля (Payoff + Greeks)  
Для блока моделирования:
- payoff на экспирацию;
- теоретический PnL при сдвиге цены/IV;
- агрегированные Greeks портфеля по сценарию.

7) Open Interest by Strike + OI change  
Добавить не только абсолютный OI по страйкам, но и изменение к предыдущему дню (`ΔOI`) и PCR по страйкам.

### По текущему ТЗ: как лучше структурировать вкладку актива
Для каждой вкладки (`SI`, `RTS`, `GOLD`, `BRENT`) рекомендуется 4 смысловых блока:
- **Market Regime**: `OHLC + exp_std bands + HV/IV spread`;
- **Vol Surface**: `Smile + Skew + Term Structure + Heatmap`;
- **Series Drilldown**: мультивыбор серий + связанные графики `Delta/Gamma/Vega/Theta`;
- **Portfolio Lab**: конструктор ног, сценарии по цене/IV, PnL и Greeks.

