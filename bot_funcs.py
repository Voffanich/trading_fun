import json
import time

import pandas as pd
from datetime import datetime as dt
import requests
import schedule

from db_funcs import db


def load_config() -> dict:
    with open('config.json') as config_file:
        return json.load(config_file)

def get_ohlcv_data_binance(pair: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        
    url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={timeframe}&limit={limit}"

    
    try:
        response = requests.get(url)
        data = response.json()
        
        ohlcv_data = [] # Only open time, open, high, low, close, volume data from response
        for candle in data:
            ohlcv = candle[0:6] # Open Time, Open, High, Low, Close, Volume
            ohlcv_data.append(ohlcv)
   
        return pd.DataFrame(ohlcv_data, columns=["O_time", "Open", "High", "Low", "Close", "Volume"])

    except ConnectionError as error:
        print('Connection error: ', error)
    except:
        print('Some another error with getting the responce from Binance')
        
    
    
def define_checked_timeframes(used_timeframes: list, timeframe: str) -> list:
    del used_timeframes[0:used_timeframes.index(timeframe)]
    return used_timeframes
        
def set_schedule(timeframe: str, task, trading_pairs: list):
    print(f'Waiting for the beginning of the {timeframe} timeframe period...\n')
    
    #running every minute tasks
        
    schedule.every().minute.at(":10").do(task, trading_pairs, True)
       
    if timeframe == "1m":
        schedule.every().minute.at(":05").do(task, trading_pairs, False)
    elif timeframe == "5m":
        schedule.every().hour.at("00:05").do(task, trading_pairs, False)
        schedule.every().hour.at("05:05").do(task, trading_pairs, False)
        schedule.every().hour.at("10:05").do(task, trading_pairs, False)
        schedule.every().hour.at("15:05").do(task, trading_pairs, False)
        schedule.every().hour.at("20:05").do(task, trading_pairs, False)
        schedule.every().hour.at("25:05").do(task, trading_pairs, False)
        schedule.every().hour.at("30:05").do(task, trading_pairs, False)
        schedule.every().hour.at("35:05").do(task, trading_pairs, False)
        schedule.every().hour.at("40:05").do(task, trading_pairs, False)
        schedule.every().hour.at("45:05").do(task, trading_pairs, False)
        schedule.every().hour.at("50:05").do(task, trading_pairs, False)
        schedule.every().hour.at("55:05").do(task, trading_pairs, False) 
    elif timeframe == "15m":
        schedule.every().hour.at("00:05").do(task, trading_pairs, False)
        schedule.every().hour.at("15:05").do(task, trading_pairs, False)
        schedule.every().hour.at("30:05").do(task, trading_pairs, False)
        schedule.every().hour.at("45:05").do(task, trading_pairs, False)
    elif timeframe == "1h":
        schedule.every().hour.at("00:05").do(task, trading_pairs, False)
    elif timeframe == "4h":
        schedule.every().day.at("00:00:05").do(task, trading_pairs, False)
        schedule.every().day.at("04:00:05").do(task, trading_pairs, False)
        schedule.every().day.at("08:00:05").do(task, trading_pairs, False)
        schedule.every().day.at("12:00:05").do(task, trading_pairs, False)
        schedule.every().day.at("16:00:05").do(task, trading_pairs, False)
        schedule.every().day.at("20:00:05").do(task, trading_pairs, False)
    elif timeframe == "1d":
        schedule.every().day.at("00:00:05").do(task, trading_pairs, False)
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

def update_active_deals(bot: object, chat_id: int, active_deals: list[object], last_candle: object):
    
    last_candle_high = float(last_candle.High)
    last_candle_low = float(last_candle.Low)
    
    for deal in active_deals:
        if deal.direction == 'long':
            if last_candle_high > deal.take_price:
                db.update_deal_data('status', 'win', deal.deal_id)
                db.update_deal_data('best_price', last_candle_high, deal.deal_id)                
                if last_candle_low < deal.worst_price:
                    db.update_deal_data('worst_price', last_candle_low, deal.deal_id)                    
                
                send_win_message(bot, chat_id, deal)
                print(f'Deal id={deal.deal_id}, {deal.pair}, {deal.direction} won')
                
            elif last_candle_low < deal.stop_price:
                db.update_deal_data('status', 'loss', deal.deal_id)
                db.update_deal_data('worst_price', last_candle_low, deal.deal_id)
                if last_candle_high > deal.best_price:
                    db.update_deal_data('best_price', last_candle_high, deal.deal_id)
                
                send_loss_message(bot, chat_id, deal)
                print(f'Deal id={deal.deal_id}, {deal.pair}, {deal.direction} lost')
                
            elif last_candle_high > deal.best_price:
                db.update_deal_data('best_price', last_candle_high, deal.deal_id)
                print('Best price updated')
                
            elif last_candle_low < deal.worst_price:
                db.update_deal_data('worst_price', last_candle_low, deal.deal_id)
                print('Worst price updated')
                
        elif deal.direction == 'short':
            if last_candle_low < deal.take_price:
                db.update_deal_data('status', 'win', deal.deal_id)
                db.update_deal_data('best_price', last_candle_low, deal.deal_id)
                if last_candle_high > deal.worst_price:
                    db.update_deal_data('worst_price', last_candle_high, deal.deal_id)
                
                send_win_message(bot, chat_id, deal)
                print(f'Deal id={deal.deal_id}, {deal.pair}, {deal.direction} won')
                
            elif last_candle_high > deal.stop_price:
                db.update_deal_data('status', 'loss', deal.deal_id)
                db.update_deal_data('worst_price', last_candle_high, deal.deal_id)
                if last_candle_low < deal.best_price:
                    db.update_deal_data('best_price', last_candle_low, deal.deal_id)
                
                send_loss_message(bot, chat_id, deal)
                print(f'Deal id={deal.deal_id}, {deal.pair}, {deal.direction} lost')
                
            elif last_candle_low < deal.best_price:
                db.update_deal_data('best_price', last_candle_low, deal.deal_id)
                print('Best price updated')
                
            elif last_candle_high > deal.worst_price:
                db.update_deal_data('worst_price', last_candle_high, deal.deal_id)
                print('Worst price updated')
            
        else:
            print('Direction of the deal is not specified!')
            

def send_win_message(bot, chat_id, deal):
    
    message = f"""
    <b>Сделка достигла тейка! Прибыль {deal.take_distance_percentage}%</b>
    
    ID: {deal.deal_id}
    Дата входа: {deal.timestamp}
    Пара: {deal.pair}
    Таймфрейм: {deal.timeframe}
    Направление: {deal.direction}
    Цена входа: {r_signif(deal.entry_price, 3)}
    Тейк: {r_signif(deal.take_price, 3)}
    Стоп: {r_signif(deal.stop_price, 3)}
    Профит-лосс: {deal.profit_loss_ratio}
    Дистанция до тейка: {deal.take_distance_percentage}%
    Дистанция до стопа: {deal.stop_distance_percentage}%
    """
    
    bot.send_message(chat_id, text=message, parse_mode = 'HTML')
    
def send_loss_message(bot, chat_id, deal):
    
    message = f"""
    <b>Сделка достигла стопа! Убыток {deal.stop_distance_percentage}%</b>
    
    ID: {deal.deal_id}
    Дата входа: {deal.timestamp}
    Пара: {deal.pair}
    Таймфрейм: {deal.timeframe}
    Направление: {deal.direction}
    Цена входа: {r_signif(deal.entry_price, 3)}
    Тейк: {r_signif(deal.take_price, 3)}
    Стоп: {r_signif(deal.stop_price, 3)}
    Профит-лосс: {deal.profit_loss_ratio}
    Дистанция до тейка: {deal.take_distance_percentage}%
    Дистанция до стопа: {deal.stop_distance_percentage}%
    """
    
    bot.send_message(chat_id, text=message, parse_mode = 'HTML')