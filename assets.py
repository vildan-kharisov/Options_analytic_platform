import requests
# req = requests.get('https://iss.moex.com/iss/apps/option-calc/v1/assets')
# assets = req.json()
# assets.sort(key=lambda x: x['asset_type'])
#
# # Упорядоченный список активов
# for i in assets:
#     print(i['asset_code'],i['title'],i['asset_type'],i['asset_subtype'])
#
# asset_type = 'futures'
# asset_subtype = ['currency','index']
#
# # Таблица из кодов, типов
# for type in asset_subtype:
#     # print(type,asset_type)
#     req = requests.get(f'https://iss.moex.com/iss/apps/option-calc/v1/assets?asset_type={asset_type}&asset_subtype={type}')
#     assets = req.json()
#     for i in assets:
#         # print(i['asset_code'],i['title'],i['asset_type'],i['asset_subtype'],sep='\t')
#         str = f'{i['asset_code']:<10s}{i['title']:<20s}{i['asset_type']:<20s}{i['asset_subtype']:<20s}'
#         print(str)
#----------------------------------------------
# {'asset_code': 'SI', 'title': 'Si (фьючерс)', 'asset_type': 'futures', 'asset_subtype': 'currency'}
# asset_code = 'SI'
# req = requests.get('https://iss.moex.com/iss/apps/option-calc/v1/assets/SI')
# asset = req.json()
# print(asset)
# #---------------------------------------------
# # Список фьючерсов
# asset_code = 'SI'
# req = requests.get(f'https://iss.moex.com/iss/apps/option-calc/v1/assets/{asset_code}/futures')
# asset = req.json()
#
# print(asset)

# for i in asset:
#     # print(i['asset_code'],i['title'],i['asset_type'],i['asset_subtype'],sep='\t')
#     str = f'{i['futures_code']:<10s}{i['asset_code']:<20s}{i['asset_type']:<20s}{i['expiration_date']:<20s}'
#     print(str)
#---------------------------------------------
schema ={
    "secid": "XXXXXXXXXXXX",
    "asset_code": "SI",
    "asset_type": "futures",
    "futures_code": "SIH6",
    "expiration_date": "2026-03-19",
    "series_type": "Q",
    "strike": 75000,
    "option_type": "call"
  }


# 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/options'
# 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/options?asset_type=futures'
# 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/options?asset_type=futures&expiration_date=2026-03-19'
# 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/options?asset_type=futures&expiration_date=2026-03-19&series_type=Q'
# 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/options?asset_type=futures&expiration_date=2026-03-19&series_type=Q&strike=75000'
# URL = f'https://iss.moex.com/iss/apps/option-calc/v1/assets/{schema["asset_code"]}/options?asset_type={schema["asset_type"]}&expiration_date={schema["expiration_date"]}&series_type={schema["series_type"]}&strike={schema["strike"]}&option_type={schema["option_type"]}'
URL = f'https://iss.moex.com/iss/apps/option-calc/v1/assets/{schema["asset_code"]}/options?asset_type={schema["asset_type"]}&expiration_date={schema["expiration_date"]}&series_type={schema["series_type"]}&option_type={schema["option_type"]}'
req = requests.get(URL)
asset = req.json()
for i in range(len(asset)):
    for k,v in asset[i].items():
        print(k,v)
    print()
    print('-----------------------------------------')
#
# # print(asset)