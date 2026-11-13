# График волатильности

# Описание запроса: Набор точек для построения графика волатильности для опционной серии.
# Точки по оси X – значения страйка, точки по оси Y – значения волатильности.
# Шаг по оси X совпадает с шагом страйка для выбранной опционной серии.
# Используются минимальное и максимальное значение среди страйков выбранной опционной серии.

import requests
from datetime import datetime

# assets = ['SI','RTS']
# asset_types = 'futures'
# def get_volatility(asset_code,asset_type):
#     today = datetime.now().date()
#     url = 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/optionseries?asset_type=futures'
#     response = requests.get(url)
#     response.raise_for_status()
#     data = response.json()
#
#     for i in data:
#         url_volatility = f'https://iss.moex.com/iss/apps/option-calc/v1/assets/{i["asset_code"]}/optionseries/{i["optionseries_code"]}/volatility_graph?asset_type={i['asset_type']}'
#         response_vol = requests.get(url_volatility)
#         response_vol.raise_for_status()
#         data_vol = response_vol.json()
#
#         #print(string)
#         for j in data_vol:
#             string = f'{i["asset_code"]:<5s}{i["futures_code"]:<10s}{i["optionseries_code"]:<20s}{i["central_strike"]:<10}{i["series_type"]:<5s}{j['strike']:<10}{j['volatility']:<10}{i["expiration_date"]:<15}{today}'
#             return string

url = 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/optionseries?asset_type=futures'
response = requests.get(url)
response.raise_for_status()
data = response.json()
print(data)