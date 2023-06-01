import json
import time

import pandas as pd
import requests
import schedule


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

def define_checked_timeframes(used_timeframes: list, timeframe: str) -> list:
    del used_timeframes[0:used_timeframes.index(timeframe)]
    return used_timeframes
        
def set_schedule(timeframe: str, task, trading_pairs: list):
    print(f'Waiting for the beginning of the {timeframe} timeframe period...\n')
    if timeframe == "1m":
        schedule.every().minute.at(":05").do(task, trading_pairs)
    elif timeframe == "5m":
        schedule.every().hour.at("00:05").do(task, trading_pairs)
        schedule.every().hour.at("05:05").do(task, trading_pairs)
        schedule.every().hour.at("10:05").do(task, trading_pairs)
        schedule.every().hour.at("15:05").do(task, trading_pairs)
        schedule.every().hour.at("20:05").do(task, trading_pairs)
        schedule.every().hour.at("25:05").do(task, trading_pairs)
        schedule.every().hour.at("30:05").do(task, trading_pairs)
        schedule.every().hour.at("35:05").do(task, trading_pairs)
        schedule.every().hour.at("40:05").do(task, trading_pairs)
        schedule.every().hour.at("45:05").do(task, trading_pairs)
        schedule.every().hour.at("50:05").do(task, trading_pairs)
        schedule.every().hour.at("55:05").do(task, trading_pairs)
    elif timeframe == "15m":
        schedule.every().hour.at("00:05").do(task, trading_pairs)
        schedule.every().hour.at("15:05").do(task, trading_pairs)
        schedule.every().hour.at("30:05").do(task, trading_pairs)
        schedule.every().hour.at("45:05").do(task, trading_pairs)
    elif timeframe == "1h":
        schedule.every().hour.at("00:05").do(task, trading_pairs)
    elif timeframe == "4h":
        schedule.every().day.at("00:00:05").do(task, trading_pairs)
        schedule.every().day.at("04:00:05").do(task, trading_pairs)
        schedule.every().day.at("08:00:05").do(task, trading_pairs)
        schedule.every().day.at("12:00:05").do(task, trading_pairs)
        schedule.every().day.at("16:00:05").do(task, trading_pairs)
        schedule.every().day.at("20:00:05").do(task, trading_pairs)
    elif timeframe == "1d":
        schedule.every().day.at("00:00:05").do(task, trading_pairs)
    else:
        print("Invalid time period string")
    
    while True:
        schedule.run_pending()
        time.sleep(1)
        
        
def r_signif(number: float, precision: int) -> float:
    """Function rounds the given float number with 0 in integer part to float number with N significant figures required.
    If given the number with integer part > 0, returns the number rounded to N - 1 figures after comma.

    Args:
        number (float): float number which abs(number) < 1 needed to be rounded
        precision (int): quantity of signigicant figures needed after rounding

    Returns:
        float: rounded to 'precision' significant figures 'number'
    """
    zero_counter = 0
    check_number = number
    
    if abs(check_number) >= 1:
        return round(number, precision - 1)
    else:
        while True:
            check_number *=10
            if abs(check_number) < 1:
                zero_counter += 1
            else:
                break
    
    return round(number, zero_counter + precision)