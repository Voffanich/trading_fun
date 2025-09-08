import json
import pprint
import threading
import time
from datetime import datetime as dt

import pandas as pd
import requests
import schedule
import telebot
from telebot import types

import aux_funcs as af
import bot_funcs as bf
import levels as lv
from cooldown import Cooldown
from db_funcs import DB_handler
from user_data.credentials import apikey3, sub1_api_key_3, sub1_api_secret_3
from binance_connect import Binance_connect
from order_manager import OrderManager
from fast_data import enable_fast_backend, fast_get_ohlcv

bot = telebot.TeleBot(apikey3)
# Enable connector file logging if enabled in config (same flag as verbose calc logging)
# Note: config loaded below; create bnc_conn after config is available

config = bf.load_config('config_5m_rm.json')
chat_id = 234637822

bnc_conn = Binance_connect(
	api_key=sub1_api_key_3,
	api_secret=sub1_api_secret_3,
	log_to_file=config['general'].get('enable_trade_calc_logging', False),
	log_file_path='logs/binance_connector.log',
	api_mode=config['general'].get('futures_api_mode', 'classic'),
)
order_manager_enabled = bool(config['general'].get('use_order_manager', False))
om = OrderManager(bnc_conn, config) if order_manager_enabled else None

# Put real bank to config for dynamic pairs filtering
try:
	bank_wallet = bnc_conn.get_usdt_balance(balance_type='wallet')
	bank_available = 0.0
	try:
		bank_available = bnc_conn.get_usdt_balance(balance_type='available')
	except Exception:
		bank_available = 0.0
	# Optional: use collateral if configured (for PM, sums cross-asset collateral)
	if bool(config['general'].get('use_pm_total_collateral', False)):
		try:
			coll = bnc_conn.get_usdt_balance(balance_type='collateral')
			if coll and coll > 0:
				bank_wallet = max(bank_wallet, coll)
				bank_available = max(bank_available, coll)
		except Exception:
			pass
	print(f"PM balances: available={bank_available}, wallet={bank_wallet}")
	if (bank_available or 0) <= 0 and (bank_wallet or 0) <= 0:
		# Force a classic read as a last resort (without switching API mode globally)
		try:
			from binance.um_futures import UMFutures as _UM
			classic = _UM(bnc_conn.api_key, bnc_conn.api_secret)
			acc = classic.account(recvWindow=60000)
			for a in (acc.get('assets', []) or []):
				if a.get('asset') == 'USDT':
					classic_available = float(a.get('availableBalance') or 0)
					classic_wallet = float(a.get('walletBalance') or a.get('marginBalance') or 0)
					bank_available = classic_available or bank_available
					bank_wallet = classic_wallet or bank_wallet
					break
		except Exception as _ex:
			print('Classic balance fallback failed:', _ex)
	config['general']['dynamic_pairs_bank'] = (bank_available or bank_wallet or config['general'].get('initial_bank_for_test_stats', 0))
	print(f"Dynamic pairs filter bank_usdt={config['general']['dynamic_pairs_bank']}")
except Exception as ex:
	print('Failed to fetch wallet/available balance for dynamic pairs filter:', ex)
	config['general']['dynamic_pairs_bank'] = config['general'].get('initial_bank_for_test_stats', 0)

# init fast backend
enable_fast_backend(use_fast=bool(config['general'].get('use_fast_data', False)),
				  timeframes=bf.define_checked_timeframes(config['general']['timeframes_used'][:], config['general']['trading_timeframe']),
				  basic_candle_depth=config['general']['basic_candle_depth'],
				  futures=True)

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
# propagate centralized logging flag into deal_config for modules using it
try:
	deal_config['enable_trade_calc_logging'] = bool(config['general'].get('enable_trade_calc_logging', False))
except Exception:
	pass
reverse = deal_config['cool_down_reverse']      # config of counting lost deals reverse or direct

cd = Cooldown(config['deal_config'], db, bot, chat_id, reverse=reverse)   



@bot.message_handler(commands=['active_deals'])
def active_deals(message):
    mess_text = db.get_active_deals_stats()
    if mess_text:
        bot.send_message(message.chat.id, text=mess_text)
    else:
        mess_text = 'No active deals found'
        bot.send_message(message.chat.id, text=mess_text)

@bot.message_handler(commands=['all_stats'])
def all_stats(message):
    mess_text = db.show_perfomance_stats(risk_per_deal=config["deal_config"]["deal_risk_perc_of_bank"], 
                                         initial_bank=config["general"]["initial_bank_for_test_stats"])
    bot.send_message(message.chat.id, text=mess_text)
    mess_text = db.show_perfomance_stats(risk_per_deal=0.03, 
                                         initial_bank=config["general"]["initial_bank_for_test_stats"])
    bot.send_message(message.chat.id, text=mess_text)
    mess_text = db.show_perfomance_stats(risk_per_deal=0.04, 
                                         initial_bank=config["general"]["initial_bank_for_test_stats"])
    bot.send_message(message.chat.id, text=mess_text)
    mess_text = db.show_perfomance_stats(risk_per_deal=0.05, 
                                         initial_bank=config["general"]["initial_bank_for_test_stats"])
    bot.send_message(message.chat.id, text=mess_text)
    mess_text = db.show_perfomance_stats_adj(best_price_perc_threshold=1, trailing_stop_perc=0.3, risk_per_deal=0.03, 
                                         initial_bank=config["general"]["initial_bank_for_test_stats"])
    bot.send_message(message.chat.id, text=mess_text)
    mess_text = db.show_perfomance_stats_adj2(best_price_perc_threshold=1, trailing_stop_perc=0.3, risk_per_deal=0.03, 
                                         initial_bank=config["general"]["initial_bank_for_test_stats"])
    bot.send_message(message.chat.id, text=mess_text)


def _get_df(pair: str, timeframe: str) -> pd.DataFrame:
    if config['general'].get('use_fast_data'):
        return fast_get_ohlcv(pair, timeframe, limit=basic_candle_depth[timeframe], futures=True)
    else:
        return bf.get_ohlcv_data_binance(pair, timeframe, limit=basic_candle_depth[timeframe], futures=True)


def check_pair(bot, chat_id, pair: str):

    levels = []       # list of levels of all checked timeframes at current moment

    for timeframe in checked_timeframes:
        df = _get_df(pair, timeframe)
        if timeframe == trading_timeframe:
            last_candle = (df.iloc[-1])    # Use the latest closed candle (schedule guarantees closure)
            basic_tf_ohlvc_df = df
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
    
    if deal != None and bf.validate_deal(db, deal, deal_config, basic_tf_ohlvc_df, validate_on=True):
        
        if not cd.status_on():
            deal.pair = pair
            
            db.add_deal(deal)
                        
            # РАЗМЕЩЕНИЕ РЕАЛЬНОЙ СДЕЛКИ НА БИНАНС
            
            # дистанция активации трейлинга в доле от дистанции до стопа в процентах
            trailing_activation_part = config['deal_config']['trailing_activation_of_stop_price']
            # протяжка трейлинга в доле от дистанции до стопа в процентах
            trailing_callback_part = config['deal_config']['trailing_callback_percent_of_stop_price']
                        
            if deal.direction == 'long':
                trailing_activation_price = deal.entry_price * (1 + trailing_activation_part * deal.stop_dist_perc / 100)
                trailing_callback_percent = round(trailing_callback_part * deal.stop_dist_perc, 1)
                side = 'BUY'
                
                print(side)
                print(f'{trailing_activation_price=}')
                print(f'{trailing_callback_percent=}')
            else:
                trailing_activation_price = deal.entry_price * (1 - trailing_activation_part * deal.stop_dist_perc / 100)
                trailing_callback_percent = round(trailing_callback_part * deal.stop_dist_perc, 1)
                side = 'SELL'
                
                print(side)
                print(f'{trailing_activation_price=}')
                print(f'{trailing_callback_percent=}')
                        
                      
            if order_manager_enabled and om:
                result = om.place_managed_trade(
                    symbol=deal.pair,
                    side=side,
                    entry_price=deal.entry_price,
                    deviation_percent=0.1,
                    stop_loss_price=deal.stop_price,
                    trailing_activation_price=trailing_activation_price,
                    trailing_callback_percent=trailing_callback_percent,
                    leverage=config['deal_config']['leverage'],
                    quantity=None,
                    risk_percent_of_bank=config['deal_config']['deal_risk_perc_of_bank'],
                    position_side='BOTH',
                    working_type='MARK_PRICE',
                    time_in_force='GTC',
                    deal_id=None,
                    verbose=config['general'].get('enable_trade_calc_logging', False),
                )
                if result.get('success'):
                    print("OK")
                else:
                    print("ERROR:", result.get('message'))
            else:
                result = bnc_conn.place_futures_order_with_protection(
                    symbol=deal.pair,
                    side=side,
                    entry_price=deal.entry_price,
                    deviation_percent=0.02,
                    stop_loss_price=deal.stop_price,
                    trailing_activation_price=trailing_activation_price,
                    trailing_callback_percent=trailing_callback_percent,
                    leverage=config['deal_config']['leverage'],
                    risk_percent_of_bank=config['deal_config']['deal_risk_perc_of_bank'],        # банк будет прочитан через account()
                    verbose=config['general'].get('enable_trade_calc_logging', False),
                )

                if result.success:
                    print("OK")
                else:
                    print("ERROR:", result.message, result.error_code)
                
            
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
                        
            Цена активации трейлинга: {af.r_signif(trailing_activation_price, 4)}
            Протяжка трейлинга: {trailing_callback_percent}%            
            """    
            
            bot.send_message(chat_id, text = deal_message)    
        else:
            cooldown_start_time = dt.strftime(cd.get_start_time(), "%Y-%m-%d %H:%M:%S")
            cooldown_finish_time = dt.strftime(cd.get_finish_time(), "%Y-%m-%d %H:%M:%S")
            
            print(f'-- Cooldown active from {cooldown_start_time} to {cooldown_finish_time}')
            
            message = f"""
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
            
            Цена активации трейлинга: {af.r_signif(trailing_activation_price, 4)}
            Протяжка трейлинга: {trailing_callback_percent}%
            
            <b>Но активна пауза с {cooldown_start_time} по {cooldown_finish_time}</b>
            """
        
            bot.send_message(chat_id, text = message, parse_mode = 'HTML') 
            

@bot.message_handler(commands=['start'])
def start(message, res=False):
    bot.send_message(message.chat.id, text="Привет, бро!")
    global chat_id
    chat_id = message.from_user.id
    print(chat_id)


@bot.message_handler(content_types=['text'])
def func(message):
        
    if ('as' in message.text or 'AS' in message.text):
        trailing_threshold = float(message.text.split(' ')[1])
        trailing_delta = float(message.text.split(' ')[2])
        
        mess_text = db.show_perfomance_stats_adj(best_price_perc_threshold=trailing_threshold, trailing_stop_perc=trailing_delta, risk_per_deal=0.03, 
                                         initial_bank=config["general"]["initial_bank_for_test_stats"])
        bot.send_message(message.chat.id, text=mess_text)        
        mess_text = db.show_perfomance_stats_adj2(best_price_perc_threshold=trailing_threshold, trailing_stop_perc=trailing_delta, risk_per_deal=0.03, 
                                         initial_bank=config["general"]["initial_bank_for_test_stats"])
        bot.send_message(message.chat.id, text=mess_text)   
    
    elif (message.text == ''):
        pass    



def main_func(trading_pairs: list, minute_flag: bool):
    
    if minute_flag:
        print(f'\nChecking active deals at {dt.strftime(dt.now(), "%Y-%m-%d %H:%M:%S")}')
    elif not minute_flag:
        print(dt.strftime(dt.now(), '%Y-%m-%d %H:%M:%S'))
        bot.send_message(chat_id, text=f"Checking candles {trading_timeframe} at {dt.strftime(dt.now(), '%Y-%m-%d %H:%M:%S')}" )   
    
    if not minute_flag:
        for pair in trading_pairs:
            print(f'Pair {pair}')
            
            try:
                check_pair(bot, chat_id, pair)
            except Exception as ex:
                print(f'{bf.timestamp()} - Some fucking error happened')
                print(ex)
                continue
            
    elif minute_flag:
        print(f"[OM heartbeat] minute cleanup tick at {dt.strftime(dt.now(), '%Y-%m-%d %H:%M:%S')}")
        bf.check_active_deals(db, cd, bot, chat_id, reverse=reverse)
        if order_manager_enabled and om:
            try:
                # Diagnostics: dump all positions
                try:
                    positions = bnc_conn.get_all_positions()
                    print("Positions (raw):")
                    for p in positions:
                        try:
                            print(p)
                        except Exception:
                            pass
                except Exception as ex:
                    print(f'Failed to fetch positions: {ex}')

                # Candidate symbols: non-zero positions
                symbols = set()
                try:
                    for s in bnc_conn.get_nonzero_position_symbols():
                        if s:
                            symbols.add(s)
                except Exception as ex:
                    print(f'Failed to get non-zero positions: {ex}')

                # Print open orders for non-zero position symbols
                for s in list(symbols):
                    try:
                        oo = bnc_conn.get_open_orders(s)
                        print(f'Open orders for {s}: {oo}')
                    except Exception as ex:
                        print(f'Failed to get open orders for {s}: {ex}')

                # Also scan configured pairs for stray open orders to catch garbage after close
                for s in trading_pairs:
                    try:
                        oo = bnc_conn.get_open_orders(s)
                        if isinstance(oo, list) and len(oo) > 0:
                            symbols.add(s)
                            print(f'Found stray open orders on {s}: {len(oo)}')
                    except Exception:
                        pass

                print(f'OrderManager cleanup: {len(symbols)} symbols => {list(symbols)}')
                for sym in symbols:
                    try:
                        om.watch_and_cleanup(sym, verbose=True)
                    except Exception as sym_ex:
                        print(f'OrderManager cleanup error for {sym}: {sym_ex}')
            except Exception as ex:
                print('OrderManager cleanup error:', ex)
        
                    
                
        
    print(f'\nWaiting for the beginning of the {trading_timeframe} timeframe period')
    # bot.send_message(chat_id, text=f'\nWaiting for the beginning of the {trading_timeframe} timeframe period')
    

# set_schedule(timeframe)
# while True:
#     schedule.run_pending()
#     time.sleep(1)

if config['general'].get('use_dynamic_trading_pairs'):
    sсheduled_tasks_thread = threading.Thread(target = bf.set_schedule_dynamic, kwargs = {'timeframe':trading_timeframe, 
                                                    'task':main_func, 'config':config}, daemon = True)
else:
    sсheduled_tasks_thread = threading.Thread(target = bf.set_schedule, kwargs = {'timeframe':trading_timeframe, 
                                                    'task':main_func, 'trading_pairs':trading_pairs}, daemon = True)
    
if __name__ == '__main__':
    sсheduled_tasks_thread.start()
    bot.infinity_polling()
    # try:
    #     bot.polling(non_stop = True, interval = 0, timeout = 0)
    # except:
    #     pass