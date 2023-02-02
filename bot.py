import json
import pprint

import pandas as pd
import requests

import bot_funcs as bf
import levels

config = bf.load_config()

pair = "ETHUSDT" # Trading pair
pair = "BTCUSDT" # Trading pair
# pair = "AKROUSDT"

timeframe = config['general']['trading_timeframe'] # Timeframe 
limit = config['levels']['candle_depth']  # Limit of candles requested 

df = bf.get_ohlcv_data_binance(pair, timeframe, limit)

levels.find_levels(df, timeframe)

