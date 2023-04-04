import json
import pprint
import time
from datetime import datetime

import pandas as pd
import requests
import schedule

import bot_funcs as bf
import levels as lv


config = bf.load_config()

pair = "ETHUSDT" # Trading pair
# pair = "API3USDT" # Trading pair
# pair = "BTCUSDT" # Trading pair
# pair = "AKROUSDT"

trading_pairs = config['general']['trading_pairs']
trading_timeframe = config['general']['trading_timeframe'] # Timeframe 
checked_timeframes = bf.define_checked_timeframes(config['general']['timeframes_used'], trading_timeframe)
limit = config['levels']['candle_depth']  # Limit of candles requested 
basic_candle_depth = config['general']['basic_candle_depth'] # number of candles to check for each checked timeframe
deal_config = config['deal_config']     # config for deal estimation



def check_pair(pair: str):
    levels = []       # list of levels of all checked timeframes at current moment

    for timeframe in checked_timeframes:
        df = bf.get_ohlcv_data_binance(pair, timeframe, limit=basic_candle_depth[timeframe])
        if timeframe == trading_timeframe:
            last_candle = (df.iloc[df.shape[0] - 2])    # OHLCV data of the last closed candle as object
        levels += lv.find_levels(df, timeframe)
        # time.sleep(0.5)
        
    levels = lv.assign_level_density(levels, checked_timeframes, config['levels'])

    levels = lv.optimize_levels(levels, checked_timeframes) # delete broken levels of the basic timeframe
    
    # lv.print_levels(levels)
    
    levels = lv.merge_timeframe_levels(levels)
    
    # lv.print_levels(levels)
    
    lv.check_deal(levels, last_candle, deal_config, trading_timeframe)

# check_pair(pair)


def main_func(trading_pairs: list):
    print(datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S'))
    for pair in trading_pairs:
        print(f'\nPair {pair}')
        check_pair(pair)

bf.set_schedule(trading_timeframe, main_func, trading_pairs)




# set_schedule(timeframe)

while True:
    schedule.run_pending()
    time.sleep(1)