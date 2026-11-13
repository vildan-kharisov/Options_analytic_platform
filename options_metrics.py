# Краткая сводка по опциону
# Описание запроса: Краткая сводка по опциону: размер комиссии, дата экспирации, последняя и расчётные цены базового актива.
# Возможность получить посчитанные значения премии (теоретической цены) и расчётных показателей по опциону,
# изменяя его параметры (цену БА, значение волатильности, количество дней до экспирации).
import requests
# base_URL = 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/options/SI75000BC6?asset_type=futures'
# # DAYS_URL ='https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/options/SI75000BC6?asset_type=futures&days_until_expiring=30'
# # PRICE_URL = 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/options/SI75000BC6?asset_type=futures&underlying_price=100'
# # IV_URL = 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/options/SI75000BC6?asset_type=futures&volatility=30'
# req = requests.get(base_URL)
# asset = req.json()
#
# for k,v in asset.items():
#     str = f'{k:<20s}{v}'
#     print(str)
# print()
# print('-----------------------------------------')

# Серии опционов на БА
# Описание запроса: Список доступных в калькуляторе опционных серий на указанный базовый актив. Отсортирован по полю expiration_date (дата экспирации) по возрастанию.
URL = 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/optionseries?asset_type=futures'
req = requests.get(URL)
asset = req.json()
for j in range(len(asset)):
    for i in asset[j]:
        str = f'{i:<20s}{asset[0][i]}'
        print(str)
    print()
    print('-----------------------------------------')

# ----------------------------------------------
# Список опционов в серии опционов
# Описание запроса: Список опционов в опционной серии.
# Отсортирован по полю strike (страйк опциона) по возрастанию.
# Параметры для фильтрации опционов в списке – страйк и тип опциона (call или put).

# 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/optionseries/SI-3.26M120226XA/options'
# URL = 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/optionseries/SI-3.26M120226XA/options?asset_type=futures&option_type=call'
# req = requests.get(URL)
# asset = req.json()
#
# for i in asset:
#     for j in i:
#         print(f'{j:<20s}{i[j]:<20}')
#     print('---------------------------------')