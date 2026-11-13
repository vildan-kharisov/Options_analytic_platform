#=======Отобранные активы==================
# 'asset_code','title','asset_type','asset_subtype'
# SI Si (фьючерс) futures currency
# RTS RTS (фьючерс) futures index
# SPYF SPYF (фьючерс) futures index
# BR BR (фьючерс) futures commodity
# GOLD GOLD (фьючерс) futures commodity
# SILV SILV (фьючерс) futures commodity
import requests
import json
from datetime import datetime

# def get_last_contract(asset_code,asset_type):
#     url = f"https://iss.moex.com/iss/apps/option-calc/v1/assets/{asset_code}/{asset_type}"
#     response = requests.get(url)
#     response.raise_for_status()
#
#     data = response.json()
#     today = datetime.now().date()
#
#     # Оставляем только контракты с датой экспирации >= сегодня
#     future_contracts = [
#         row for row in data
#         if datetime.strptime(row["expiration_date"], "%Y-%m-%d").date() >= today
#     ]
#     if not future_contracts:
#         string = "Нет активных контрактов"
#         return string
#     else:
#         nearest = min(
#             future_contracts,
#             key=lambda row: datetime.strptime(row["expiration_date"], "%Y-%m-%d").date() - today
#         )
#         return(json.dumps(nearest, indent=2, ensure_ascii=False))
# # assets = ['SI','RTS','SPYF','BR','GOLD','SILV']
# assets = ['SI']
# types = 'futures'
# for asset in assets:
#     print(get_last_contract(asset,types))

#------------------------------------------------
assets = ['RTS']
types = 'futures'

# def get_volatility(asset_code,asset_type):
today = datetime.now().date()
url = 'https://iss.moex.com/iss/apps/option-calc/v1/assets/RTS/optionseries?asset_type=futures'

response = requests.get(url)
response.raise_for_status()
data = response.json()

for i in data:
    url_iv = f'https://iss.moex.com/iss/apps/option-calc/v1/assets/{i["asset_code"]}/optionseries/{i["optionseries_code"]}/optionboard?asset_type={i['asset_type']}&rows=0'
    response_iv = requests.get(url_iv)
    response_iv.raise_for_status()
    data_iv = response_iv.json()
    # print(data_iv["call"][0])
    #string = f'{i["asset_code"]:<5s}{i["futures_code"]:<10s}{i["optionseries_code"]:<20s}{i["central_strike"]:<10}{i["series_type"]:<5s}{data_iv['call'][0]['volatility']:<10}{i["expiration_date"]:<15}{today}'
    #string = f'{i["asset_code"]:<5s}{i["futures_code"]:<10s}{i["optionseries_code"]:<20s}{i["central_strike"]:<10}{i["series_type"]:<5s}{data_iv['call'][0]['offer']:<10}{data_iv['call'][0]['bid']:<10}{i["expiration_date"]:<15}{today}'
    print(data_iv)
    print('----------------------------------------------------------------------------------------')
#
#
#
#
#
# print(data)