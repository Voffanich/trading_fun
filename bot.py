import pandas as pd
import requests

import levels

pair = "ETHUSDT" # Trading pair
interval = "1h" # Timeframe 
limit = 1000 # Limit of candles requested 


url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={interval}&limit={limit}"

response = requests.get(url)
data = response.json()

ohlcv_data = [] # Only open time, open, high, low, close, volume data from response
for candle in data:
    ohlcv = candle[0:6] # Open Time, Open, High, Low, Close, Volume
    ohlcv_data.append(ohlcv)
   

df = pd.DataFrame(ohlcv_data, columns=["O_time", "Open", "High", "Low", "Close", "Volume"])
# print(df)

levels.find_levels(df)

