import json
import pprint
import time
from datetime import datetime

import pandas as pd
import requests
import schedule

import bot_funcs as bf
import levels as lv


def test_check(timeframe):
    print(f'timeframe = {timeframe}, timestampt: {datetime.now()}')

def set_schedule(timeframe):
    if timeframe == "1m":
        schedule.every().minute.at(":05").do(test_check, timeframe)
    elif timeframe == "5m":
        schedule.every().hour.at("00:05").do(test_check, timeframe)
        schedule.every().hour.at("05:05").do(test_check, timeframe)
        schedule.every().hour.at("10:05").do(test_check, timeframe)
        schedule.every().hour.at("15:05").do(test_check, timeframe)
        schedule.every().hour.at("20:05").do(test_check, timeframe)
        schedule.every().hour.at("25:05").do(test_check, timeframe)
        schedule.every().hour.at("30:05").do(test_check, timeframe)
        schedule.every().hour.at("35:05").do(test_check, timeframe)
        schedule.every().hour.at("40:05").do(test_check, timeframe)
        schedule.every().hour.at("45:05").do(test_check, timeframe)
        schedule.every().hour.at("50:05").do(test_check, timeframe)
        schedule.every().hour.at("55:05").do(test_check, timeframe)
    elif timeframe == "15m":
        schedule.every().hour.at("00:05").do(test_check, timeframe)
        schedule.every().hour.at("15:05").do(test_check, timeframe)
        schedule.every().hour.at("30:05").do(test_check, timeframe)
        schedule.every().hour.at("45:05").do(test_check, timeframe)
    elif timeframe == "1h":
        schedule.every().hour.at("00:05").do(test_check, timeframe)
    elif timeframe == "4h":
        schedule.every().day.at("00:00:05").do(test_check, timeframe)
        schedule.every().day.at("04:00:05").do(test_check, timeframe)
        schedule.every().day.at("08:00:05").do(test_check, timeframe)
        schedule.every().day.at("12:00:05").do(test_check, timeframe)
        schedule.every().day.at("16:00:05").do(test_check, timeframe)
        schedule.every().day.at("20:00:05").do(test_check, timeframe)
    elif timeframe == "1d":
        schedule.every().day.at("00:00:05").do(test_check, timeframe)
    else:
        print("Invalid time period string")



config = bf.load_config()

pair = "ETHUSDT" # Trading pair
# pair = "API3USDT" # Trading pair
# pair = "BTCUSDT" # Trading pair
# pair = "AKROUSDT"

timeframe = config['general']['trading_timeframe'] # Timeframe 
checked_timeframes = bf.define_checked_timeframes(config['general']['timeframes_used'], timeframe)
limit = config['levels']['candle_depth']  # Limit of candles requested 
basic_candle_depth = config['general']['basic_candle_depth'] # number of candles to check for each checked timeframe

levels = []       # list of levels of all checked timeframes at current moment

for timeframe in checked_timeframes:
    df = bf.get_ohlcv_data_binance(pair, timeframe, limit=basic_candle_depth[timeframe])
    levels += lv.find_levels(df, timeframe)

levels = lv.assign_level_density(levels, checked_timeframes, config['levels'])

levels = lv.optimize_levels(levels, checked_timeframes)

for level in levels:
        print(level)



# set_schedule(timeframe)

# while True:
#     schedule.run_pending()
#     time.sleep(1)