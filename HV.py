import numpy as np
import pandas as pd
from scipy import stats

def calculate_historical_volatility(ticker, period='1y', window=20, trading_days=252):
    """
    Рассчитывает историческую волатильность для заданного тикера
    
    Parameters:
    ticker (str): Символ акции или ETF
    period (str): Период для загрузки данных ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
    window (int): Окно для расчета волатильности (в днях)
    trading_days (int): Количество торговых дней в году для аннуализации
    
    Returns:
    DataFrame: Датафрейм с ценами, доходностями и волатильностью
    """
    # Загрузка данных с auto_adjust=False
    data = yf.download(ticker, period=period, auto_adjust=False)
    
    # Расчет логарифмических доходностей
    data['log_return'] = np.log(data['Close'] / data['Close'].shift(1))
    
    # Расчет скользящей волатильности
    data['volatility'] = data['log_return'].rolling(window=window).std() * np.sqrt(trading_days)
    
    # Расчет полной исторической волатильности за весь период
    full_period_vol = data['log_return'].std() * np.sqrt(trading_days)
    print(f"\n Историческая волатильность {ticker} за весь период: {full_period_vol:.4f} ({full_period_vol*100:.2f}%)")
    
    return data