# import requests
# URL = 'http://iss.moex.com/iss/iss/securities/IMOEX/agregates.dates (2026-02-06)'
# req = requests.get(URL)
# print(req.json())


#---------------------------------------------------------------------------

# Ближайший контракт: Si-3.26 (SiH6)
# Экспирация:         19.03.2026
# Откр. позиции:      9,424,992
# Последняя цена:     77696
# Объём сегодня:      20105


import requests
import xml.etree.ElementTree as ET
import pandas as pd


def parse_moex_xml(url: str) -> dict[str, pd.DataFrame]:
    response = requests.get(url)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    result = {}
    for block in root.findall("data"):
        rows = [row.attrib for row in block.findall(".//row")]
        if rows:
            result[block.get("id")] = pd.DataFrame(rows)
    return result


url = "https://iss.moex.com/iss/engines/futures/markets/forts/securities.xml?sectypes=si"
data = parse_moex_xml(url)

sec = data["securities"]
md = data["marketdata"]

# Приводим типы
sec["LASTTRADEDATE"] = pd.to_datetime(sec["LASTTRADEDATE"])
sec["PREVOPENPOSITION"] = pd.to_numeric(sec["PREVOPENPOSITION"])

# Ближайший контракт = максимальный открытый интерес
nearest = sec.sort_values("PREVOPENPOSITION", ascending=False).iloc[0]
ticker = nearest["SECID"]

print(f"Ближайший контракт: {nearest['SHORTNAME']} ({ticker})")
print(f"Экспирация:         {nearest['LASTTRADEDATE'].strftime('%d.%m.%Y')}")
print(f"Откр. позиции:      {nearest['PREVOPENPOSITION']:,.0f}")

# Котировки ближайшего
quote = md[md["SECID"] == ticker].iloc[0]
print(f"Последняя цена:     {quote['LAST']}")
print(f"Объём сегодня:      {quote['VOLTODAY']}")

#---------------------------------------------------------------------------
# import requests
# import xml.etree.ElementTree as ET
# import pandas as pd
#
#
# def parse_moex_xml(url: str) -> dict[str, pd.DataFrame]:
#     """Парсит XML с MOEX ISS и возвращает dict блоков в виде DataFrame."""
#     response = requests.get(url)
#     response.raise_for_status()
#     root = ET.fromstring(response.content)
#
#     result = {}
#     for data_block in root.findall("data"):
#         block_id = data_block.get("id")
#         rows = [row.attrib for row in data_block.findall(".//row")]
#         if rows:
#             result[block_id] = pd.DataFrame(rows)
#     return result
#
#
# url = "https://iss.moex.com/iss/engines/futures/markets/forts/securities.xml?sectypes=si"
# data = parse_moex_xml(url)
#
# # --- Справочные данные по контрактам ---
# sec = data["securities"]
# print("=== Фьючерсы Si ===")
# print(sec[["SECID", "SHORTNAME", "LASTTRADEDATE", "PREVSETTLEPRICE",
#            "INITIALMARGIN", "HIGHLIMIT", "LOWLIMIT", "PREVOPENPOSITION"]].to_string(index=False))
#
# # --- Рыночные данные ---
# md = data["marketdata"]
# print("\n=== Котировки ===")
# print(md[["SECID", "OPEN", "HIGH", "LOW", "LAST",
#           "SETTLEPRICE", "VOLTODAY", "OPENPOSITION"]].to_string(index=False))


#----------------------------------------------
# import requests
# import xml.etree.ElementTree as ET
# import pandas as pd
#
# url = "https://iss.moex.com/iss/statistics/engines/futures/markets/options/openpositions/SI.xml"
# response = requests.get(url)
# root = ET.fromstring(response.content)
#
# block = root.find(".//data[@id='open_positions']")
# rows = [row.attrib for row in block.findall(".//row")]
# df = pd.DataFrame(rows)
#
# # Приводим числовые колонки
# numeric_cols = [
#     "is_fiz", "persons_long", "persons_short",
#     "open_position_long", "open_position_short",
#     "oichange_long", "oichange_short",
# ]
# df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)
#
# # Расшифровываем поля для удобства
# df["holder"] = df["is_fiz"].map({0: "Юрлица", 1: "Физлица"})
# df["asset_type_name"] = df["asset_type"].map({"F": "Фьючерс", "S": "Спот"})
# df["option_type_name"] = df["option_type"].map({"C": "Call", "P": "Put"})
#
# print(df[["tradedate", "asset", "asset_type_name", "option_type_name", "holder",
#           "persons_long", "persons_short",
#           "open_position_long", "open_position_short",
#           "oichange_long", "oichange_short"]].to_string(index=False))