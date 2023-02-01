import json
import pprint

import pandas as pd
import requests

import levels

with open('config.json') as config_file:
    config = json.load(config_file)

pair = "ETHUSDT" # Trading pair
pair = "BTCUSDT" # Trading pair
# pair = "AKROUSDT"
timeframe = config['general']['trading_timeframe'] # Timeframe 
limit = config['levels']['candle_depth']  # Limit of candles requested 


url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={timeframe}&limit={limit}"

response = requests.get(url)
data = response.json()

ohlcv_data = [] # Only open time, open, high, low, close, volume data from response
for candle in data:
    ohlcv = candle[0:6] # Open Time, Open, High, Low, Close, Volume
    ohlcv_data.append(ohlcv)
   

df = pd.DataFrame(ohlcv_data, columns=["O_time", "Open", "High", "Low", "Close", "Volume"])
# print(df)

levels.find_levels(df, timeframe)

