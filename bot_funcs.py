import json

import pandas as pd
import requests


def load_config() -> dict:
    with open('config.json') as config_file:
        return json.load(config_file)

def get_ohlcv_data_binance(pair: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        
    url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={timeframe}&limit={limit}"

    response = requests.get(url)
    data = response.json()

    ohlcv_data = [] # Only open time, open, high, low, close, volume data from response
    for candle in data:
        ohlcv = candle[0:6] # Open Time, Open, High, Low, Close, Volume
        ohlcv_data.append(ohlcv)
   
    return pd.DataFrame(ohlcv_data, columns=["O_time", "Open", "High", "Low", "Close", "Volume"])
        