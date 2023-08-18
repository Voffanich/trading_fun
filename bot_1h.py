import json
import pprint
import threading
import time
from datetime import datetime

import pandas as pd
import requests
import schedule
import telebot
from telebot import types

import aux_funcs as af
import bot_funcs as bf
import levels as lv
from db_funcs import DB_handler
from user_data.credentials import apikey2

bot = telebot.TeleBot(apikey2)

config = bf.load_config('config_1h.json')
chat_id = 234637822

db = DB_handler(config["general"]["db_file_name"])
db.setup()

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

   

def check_pair(bot, chat_id, pair: str, minute_flag: bool):

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

    deal = lv.check_deal(bot, chat_id, levels, last_candle, deal_config, trading_timeframe)
    print(f'{deal=}')
    
    if deal:
        print('\n')
    
    if deal != None and bf.validate_deal(db, deal, deal_config, validate_on=True):
        
        deal.pair = pair
        
        db.add_deal(deal)
        
        deal_message = f"""
        Найдена сделка:
        
        Пара: {deal.pair}
        Таймфрейм: {deal.timeframe}
        Направление: {deal.direction}
        Цена входа: {af.r_signif(deal.entry_price, 4)}
        Тейк: {af.r_signif(deal.take_price, 4)}
        Стоп: {af.r_signif(deal.stop_price, 4)}
        Профит-лосс: {deal.profit_loss_ratio}
        Дистанция до тейка: {deal.take_dist_perc}%
        Дистанция до стопа: {deal.stop_dist_perc}%
        """
    
        bot.send_message(chat_id, text = deal_message)    
      

@bot.message_handler(commands=['start'])
def start(message, res=False):
    bot.send_message(message.chat.id, text="Привет, бро!")
    global chat_id
    chat_id = message.from_user.id
    print(chat_id)
    

def main_func(trading_pairs: list, minute_flag: bool):
    
    if minute_flag:
        print(f'\nChecking active deals at {datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")}')
    elif not minute_flag:
        print(datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S'))
        bot.send_message(chat_id, text=f"Checking candles {trading_timeframe} at {datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')}")   
    
    if not minute_flag:
        for pair in trading_pairs:
            print(f'Pair {pair}')
            
            try:
                check_pair(bot, chat_id, pair, minute_flag)
            except Exception as ex:
                print(f'{bf.timestamp()} - Some fucking error happened')
                print(ex)
                continue
            
    elif minute_flag:
        bf.check_active_deals(db, bot, chat_id)
                
        
    print(f'\nWaiting for the beginning of the {trading_timeframe} timeframe period')
    # bot.send_message(chat_id, text=f'\nWaiting for the beginning of the {trading_timeframe} timeframe period')
    

# set_schedule(timeframe)
# while True:
#     schedule.run_pending()
#     time.sleep(1)

sсheduled_tasks_thread = threading.Thread(target = bf.set_schedule, kwargs = {'timeframe':trading_timeframe, 
                                                    'task':main_func, 'trading_pairs':trading_pairs}, daemon = True)
    
if __name__ == '__main__':
    sсheduled_tasks_thread.start()
    try:
        bot.polling(non_stop = True, interval = 0, timeout = 0)
    except:
        pass