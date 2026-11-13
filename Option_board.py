import requests
# Доска опционов
# Описание запроса: Доска опционов для опционной серии по её коду.
# Ответ содержит список call-опционов и список put-опционов, внутри списка опционы отсортированы по полю strike по возрастанию.
# Содержит расчётные параметры для каждого опциона в серии, значения теоретической цены и волатильности, внутренней стоимости.

# URL = 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/optionseries/SI-3.26M120226XA/optionboard?rows=10'
# req = requests.get(URL)
# asset = req.json()
# type = ['call']#,'put'
# for j in type:
#     for i in asset[j]:
#         print(i)

#--------------------------------------------------------------------
# График волатильности

# Описание запроса: Набор точек для построения графика волатильности для опционной серии.
# Точки по оси X – значения страйка, точки по оси Y – значения волатильности.
# Шаг по оси X совпадает с шагом страйка для выбранной опционной серии.
# Используются минимальное и максимальное значение среди страйков выбранной опционной серии.

URL = 'https://iss.moex.com/iss/apps/option-calc/v1/assets/SI/optionseries/SI-3.26M120226XA/volatility_graph?asset_type=futures'
req = requests.get(URL)
asset = req.json()
for i in asset:
    print(i['strike'],i['volatility'])

