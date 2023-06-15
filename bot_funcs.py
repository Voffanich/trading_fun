import json
import time
from datetime import datetime as dt

import pandas as pd
import requests
import schedule

import aux_funcs as af
from db_funcs import db


def timestamp() -> str:
    return dt.strftime(dt.now(), "%Y-%m-%d %H:%M:%S")

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
        print(f'{timestamp()} - Connection error: ', error)
    except:
        print(f'{timestamp()} - Some another error with getting the responce from Binance')
        
    
    
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
        

def update_current_deal_price(deal: object, current_price: float):
    
    if deal.direction == 'long':
        current_price_perc = round((current_price - deal.entry_price) / deal.entry_price * 100, 2)
    elif deal.direction == 'short':
        current_price_perc = round((current_price - deal.entry_price) / deal.entry_price * 100, 2) * -1
        
        
    
    db.update_deal_data('current_price', current_price, deal.deal_id)
    db.update_deal_data('current_price_perc', current_price_perc, deal.deal_id)
    
def update_best_price(deal: object, best_price: float):
    
    best_price_perc = abs(round((best_price - deal.entry_price) / deal.entry_price * 100, 2))
    
    db.update_deal_data('best_price', af.r_signif(best_price, 4), deal.deal_id)
    db.update_deal_data('best_price_perc', best_price_perc, deal.deal_id)


def update_worst_price(deal: object, worst_price: float):
    
    worst_price_perc = abs(round((worst_price - deal.entry_price) / deal.entry_price * 100, 2))
    
    db.update_deal_data('worst_price', af.r_signif(worst_price, 4), deal.deal_id)
    db.update_deal_data('worst_price_perc', worst_price_perc, deal.deal_id)


def update_active_deals(bot: object, chat_id: int, active_deals: list[object], last_candle: object):
    
    last_candle_high = af.r_signif(float(last_candle.High), 4)
    last_candle_low = af.r_signif(float(last_candle.Low), 4)
    last_cande_close = af.r_signif(float(last_candle.Close), 4)
    
    for deal in active_deals:
        
        update_current_deal_price(deal, last_cande_close)
        
        if deal.direction == 'long':
            
            if last_candle_high > deal.take_price:
                db.update_deal_data('status', 'win', deal.deal_id)
                db.update_deal_data('finish_time', timestamp(), deal.deal_id)
                update_best_price(deal, last_candle_high)
                             
                if last_candle_low < deal.worst_price:
                    update_worst_price(deal, last_candle_low)                    
                    
                send_win_message(bot, chat_id, deal)
                print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Won')
                
            elif last_candle_low < deal.stop_price:
                db.update_deal_data('status', 'loss', deal.deal_id)
                db.update_deal_data('finish_time', timestamp(), deal.deal_id)
                update_worst_price(deal, last_candle_low) 
                if last_candle_high > deal.best_price:
                    update_best_price(deal, last_candle_high)
                
                send_loss_message(bot, chat_id, deal)
                print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Lost')
                
            elif last_candle_high > deal.best_price:
                update_best_price(deal, last_candle_high)
                print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Best price updated')
                                
            elif last_candle_low < deal.worst_price:
                update_worst_price(deal, last_candle_low) 
                print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Worst price updated')
                              
        elif deal.direction == 'short':
            
            if last_candle_low < deal.take_price:
                db.update_deal_data('status', 'win', deal.deal_id)
                db.update_deal_data('finish_time', timestamp(), deal.deal_id)
                update_best_price(deal, last_candle_low)
                
                if last_candle_high > deal.worst_price:
                    update_worst_price(deal, last_candle_high) 
                
                send_win_message(bot, chat_id, deal)
                print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Won')
                
            elif last_candle_high > deal.stop_price:
                db.update_deal_data('status', 'loss', deal.deal_id)
                db.update_deal_data('finish_time', timestamp(), deal.deal_id)
                update_worst_price(deal, last_candle_high)
                if last_candle_low < deal.best_price:
                    update_best_price(deal, last_candle_low)
                
                send_loss_message(bot, chat_id, deal)
                print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Lost')
                
            elif last_candle_low < deal.best_price:
                update_best_price(deal, last_candle_low)
                print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Best price updated')
                            
            elif last_candle_high > deal.worst_price:
                update_worst_price(deal, last_candle_high)
                print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Worst price updated')
                           
        else:
            print('Direction of the deal is not specified!')
            

def send_win_message(bot, chat_id, deal):
    
    message = f"""
    <b>Сделка достигла тейка! Прибыль {deal.take_dist_perc}%</b>
    
    ID: {deal.deal_id}
    Дата входа: {deal.timestamp}
    Пара: {deal.pair}
    Таймфрейм: {deal.timeframe}
    Направление: {deal.direction}
    Цена входа: {af.r_signif(deal.entry_price, 3)}
    Тейк: {af.r_signif(deal.take_price, 3)}
    Стоп: {af.r_signif(deal.stop_price, 3)}
    Профит-лосс: {deal.profit_loss_ratio}
    Дистанция до тейка: {deal.take_dist_perc}%
    Дистанция до стопа: {deal.stop_dist_perc}%
    """
    
    bot.send_message(chat_id, text=message, parse_mode = 'HTML')
    
def send_loss_message(bot, chat_id, deal):
    
    message = f"""
    <b>Сделка достигла стопа! Убыток {deal.stop_dist_perc}%</b>
    
    ID: {deal.deal_id}
    Дата входа: {deal.timestamp}
    Пара: {deal.pair}
    Таймфрейм: {deal.timeframe}
    Направление: {deal.direction}
    Цена входа: {af.r_signif(deal.entry_price, 3)}
    Тейк: {af.r_signif(deal.take_price, 3)}
    Стоп: {af.r_signif(deal.stop_price, 3)}
    Профит-лосс: {deal.profit_loss_ratio}
    Дистанция до тейка: {deal.take_dist_perc}%
    Дистанция до стопа: {deal.stop_dist_perc}%
    """
    
    bot.send_message(chat_id, text=message, parse_mode = 'HTML')
    
    
def check_active_deals(bot, chat_id):
    
    active_deal_pairs = db.get_active_deals_list()
    # print(f'{active_deal_pairs=}')
    
    for pair in active_deal_pairs:
                
        df = get_ohlcv_data_binance(pair, '1m', limit=2)
        last_candle = (df.iloc[df.shape[0] - 2])    # OHLCV data of the last closed candle as object
        
        # get active deals from database    
        active_deals = db.read_active_deals(pair)
        #check and update active deals for result or best/worst price
        update_active_deals(bot, chat_id, active_deals, last_candle)  