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

import bot_funcs as bf
import levels as lv
from db_funcs import db
from user_data.credentials import apikey

bot = telebot.TeleBot(apikey)
db.setup()

config = bf.load_config()
chat_id = 234637822

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



def check_pair(bot, chat_id, pair: str):
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
    
    if deal != None:
        
        deal.pair = pair
        
        db.add_deal(deal)
        
        deal_message = f"""
        Найдена сделка:
        
        Пара: {deal.pair}
        Таймфрейм: {deal.timeframe}
        Направление: {deal.direction}
        Цена входа: {bf.r_signif(deal.entry_price, 4)}
        Тейк: {bf.r_signif(deal.take_price, 4)}
        Стоп: {bf.r_signif(deal.stop_price, 4)}
        Профит-лосс: {deal.profit_loss_ratio}
        Дистанция до тейка: {deal.take_distance_percentage}%
        Дистанция до стопа: {deal.stop_distance_percentage}%
        """
    
        bot.send_message(chat_id, text = deal_message)
        
    # get active deals from database    
    active_deals = db.read_active_deals(pair)
    
    #check and update active deals for result or best/worst price
    bf.update_active_deals(bot, chat_id, active_deals, last_candle)    


# check_pair(pair)


@bot.message_handler(commands=['start'])
def start(message, res=False):
    bot.send_message(message.chat.id, text="Привет, бро!")
    global chat_id
    chat_id = message.from_user.id
    print(chat_id)
    

def main_func(trading_pairs: list):
    print(datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S'))
    bot.send_message(chat_id, text=f"Checking candles {trading_timeframe} at {datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')}")
    for pair in trading_pairs:
        print(f'\nPair {pair}')
        check_pair(bot, chat_id, pair)
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