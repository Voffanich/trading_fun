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
from binance_connector import ClassicIMConnector, PortfolioPMConnector
from order_manager import OrderManager
from fast_data import enable_fast_backend, fast_get_ohlcv

bot = telebot.TeleBot(apikey3)
# Enable connector file logging if enabled in config (same flag as verbose calc logging)
# Note: config loaded below; create bnc_conn after config is available

config = bf.load_config('config_5m_rm.json')
chat_id = 234637822

# Initialize connector (IM classic or PM portfolio)
api_mode = config['general'].get('futures_api_mode', 'classic')
use_pm = (str(api_mode).lower() in ('pm', 'portfolio', 'portfolio_margin'))
if use_pm:
	bnc_conn = PortfolioPMConnector(api_key=sub1_api_key_3, api_secret=sub1_api_secret_3, recv_window_ms=60000, log=bool(config['general'].get('enable_trade_calc_logging', False)))
else:
	bnc_conn = ClassicIMConnector(api_key=sub1_api_key_3, api_secret=sub1_api_secret_3, recv_window_ms=60000, log=bool(config['general'].get('enable_trade_calc_logging', False)))

order_manager_enabled = bool(config['general'].get('use_order_manager', True))
om = OrderManager(bnc_conn, config) if order_manager_enabled else None

# Put real bank to config for dynamic pairs filtering
try:
	# Use collateral equity consistently for dynamic pairs filtering
	bank_equity = 0.0
	try:
		bank_equity = bnc_conn.get_usdt_balance(balance_type='collateral')
	except Exception:
		pass
	print(f"[PAIRS] Bank (equity/collateral)={bank_equity}")
	# Prefer equity; if zero/unavailable, fallback to wallet; then to initial from config
	try:
		bank_wallet = bnc_conn.get_usdt_balance(balance_type='wallet')
	except Exception:
		bank_wallet = 0.0
	chosen_bank = bank_equity if (bank_equity and bank_equity > 0) else (bank_wallet if (bank_wallet and bank_wallet > 0) else float(config['general'].get('initial_bank_for_test_stats', 0) or 0))
	config['general']['dynamic_pairs_bank'] = chosen_bank
	print(f"[PAIRS] Dynamic bank_usdt={config['general']['dynamic_pairs_bank']}")
except Exception as ex:
	print('[PAIRS] Failed to fetch balances for dynamic pairs filter:', ex)
	config['general']['dynamic_pairs_bank'] = config['general'].get('initial_bank_for_test_stats', 0)

# Local dynamic trading pairs selection (first/working one)
from datetime import datetime, timedelta

def _fetch_24h_tickers() -> list:
	try:
		r = requests.get('https://fapi.binance.com/fapi/v1/ticker/24hr', timeout=10)
		r.raise_for_status()
		return r.json()
	except Exception as e:
		print('[PAIRS] fetch 24h failed:', e)
		return []


def _fetch_exchange_filters() -> dict:
	"""Return mapping: symbol -> {filterType: filterDict} using one exchangeInfo call."""
	try:
		r = requests.get('https://fapi.binance.com/fapi/v1/exchangeInfo', timeout=10)
		r.raise_for_status()
		info = r.json() or {}
		m = {}
		for s in info.get('symbols', []):
			fs = {}
			for f in s.get('filters', []):
				ft = f.get('filterType')
				if ft:
					fs[ft] = f
			m[s.get('symbol')] = fs
		return m
	except Exception as e:
		print('[PAIRS] fetch exchangeInfo failed:', e)
		return {}


def select_trading_pairs(count: int = 30) -> list:
	bank_usdt = float(config['general'].get('dynamic_pairs_bank', 0) or 0)
	risk = float(config['deal_config'].get('deal_risk_perc_of_bank', 0.0))
	# предполагаемая минимальная дистанция до стопа (%, из конфига для отбора пар)
	stop_perc = float(config['deal_config'].get('selection_stop_distance_perc', 1.0))
	stop_pct = max(0.01, stop_perc) / 100.0
	leverage = float(config['deal_config'].get('leverage', 1) or 1)
	print(f"[PAIRS] Selecting top {count} by 24h quoteVolume; risk={risk}, bank={bank_usdt}, stop%={stop_perc}")
	data = _fetch_24h_tickers()
	# Pre-sort by quote volume, then consider only top_k for filter evaluation to speed up
	tmp = []
	for d in data:
		try:
			sym = d.get('symbol')
			if not sym or not sym.endswith('USDT') or '_' in sym:
				continue
			qvol = float(d.get('quoteVolume', 0) or 0)
			last_price = float(d.get('lastPrice', 0) or 0)
			tmp.append((sym, qvol, last_price))
		except Exception:
			continue
	tmp.sort(key=lambda x: x[1], reverse=True)
	top_k = tmp[:max(count * 4, 120)]  # cap checks to first N
	filters_map = _fetch_exchange_filters()
	cands = []
	for sym, qvol, last_price in top_k:
		fs = filters_map.get(sym) or {}
		try:
			mnf = fs.get('MIN_NOTIONAL', {})
			min_notional = float(mnf.get('notional', mnf.get('minNotional', 0)) or 0)
		except Exception:
			min_notional = 0.0
		try:
			lsf = fs.get('LOT_SIZE', {})
			min_qty = float(lsf.get('minQty', 0) or 0)
			step = float(lsf.get('stepSize', 0) or 0)
		except Exception:
			min_qty, step = 0.0, 0.0
		# compute risk-based qty (loss ~= notional * stop_pct); leverage does not change loss vs notional
		ok = True
		if last_price <= 0 or stop_pct <= 0 or bank_usdt <= 0 or risk <= 0:
			ok = False
		else:
			risk_amount = bank_usdt * (risk / 100.0)
			qty_risk = risk_amount / (last_price * stop_pct)
			# round DOWN to step; do not increase qty to avoid raising risk
			if step > 0:
				steps = int(qty_risk / step)
				qty_rounded = steps * step
			else:
				qty_rounded = qty_risk
			# validate rounded qty
			if qty_rounded < max(min_qty, 0):
				ok = False
			else:
				notional = qty_rounded * last_price
				if min_notional > 0 and notional < min_notional:
					ok = False
		cands.append({
			"symbol": sym,
			"quoteVolume": qvol,
			"eligible": ok
		})
	# sort by quoteVolume desc
	cands.sort(key=lambda x: x['quoteVolume'], reverse=True)
	selected = [c['symbol'] for c in cands if c['eligible']][:count]
	print(f"[PAIRS] Eligible count={sum(1 for c in cands if c['eligible'])} / total_checked={len(cands)}")
	print(f"[PAIRS] Selected ({len(selected)}): {', '.join(selected)}")
	return selected


def schedule_daily_pairs_refresh():
	def _worker():
		while True:
			now = datetime.now()
			next_run = (now + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
			sleep_sec = max(1, int((next_run - now).total_seconds()))
			time.sleep(sleep_sec)
			try:
				pairs = select_trading_pairs(30)
				if pairs:
					global trading_pairs
					trading_pairs = pairs
					print('[PAIRS] Daily refresh applied')
			except Exception as e:
				print('[PAIRS] Daily refresh failed:', e)
	thr = threading.Thread(target=_worker, daemon=True)
	thr.start()

# init fast backend
enable_fast_backend(use_fast=bool(config['general'].get('use_fast_data', False)),
				  timeframes=bf.define_checked_timeframes(config['general']['timeframes_used'][:], config['general']['trading_timeframe']),
				  basic_candle_depth=config['general']['basic_candle_depth'],
				  futures=True)

db = DB_handler(config["general"]["db_file_name"])
db.setup()

# initial pairs selection (first/working)
trading_pairs = select_trading_pairs(30)
schedule_daily_pairs_refresh()

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

    last_candle = None
    basic_tf_ohlvc_df = None

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

    if last_candle is None or basic_tf_ohlvc_df is None:
        return

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
                    balance_type='collateral',
                )
                if result.get('success'):
                    print("OK")
                else:
                    print("ERROR:", result.get('message'))
            else:
                # Legacy direct connector branch is disabled for new PM/IM connector
                print("OrderManager disabled by config; skipping direct placement.")
            
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
    
    # always use dynamically refreshed global list selected by our first-stage filter
    try:
        current_pairs = list(globals().get('trading_pairs', []) or [])
    except Exception:
        current_pairs = trading_pairs
    
    if minute_flag:
        print(f'\nChecking active deals at {dt.strftime(dt.now(), "%Y-%m-%d %H:%M:%S")}')
    elif not minute_flag:
        # explicit boundary calc start log
        print(f"[TF] {trading_timeframe} boundary at {dt.strftime(dt.now(), '%Y-%m-%d %H:%M:%S')} — starting deals calculation for {len(current_pairs)} pairs")
        print(dt.strftime(dt.now(), '%Y-%m-%d %H:%M:%S'))
        bot.send_message(chat_id, text=f"Checking candles {trading_timeframe} at {dt.strftime(dt.now(), '%Y-%m-%d %H:%M:%S')}" )   
    
    if not minute_flag:
        for pair in current_pairs:
            print(f'Pair {pair}')
            
            try:
                check_pair(bot, chat_id, pair)
            except Exception as ex:
                print(f'{bf.timestamp()} - Some fucking error happened')
                print(ex)
                continue
        # explicit end log for timeframe calc
        print(f"[TF] {trading_timeframe} boundary calculation finished at {dt.strftime(dt.now(), '%Y-%m-%d %H:%M:%S')}")
        
    elif minute_flag:
        bf.check_active_deals(db, cd, bot, chat_id, reverse=reverse)
        
                     
                
        
    print(f'\nWaiting for the beginning of the {trading_timeframe} timeframe period')
    # bot.send_message(chat_id, text=f'\nWaiting for the beginning of the {trading_timeframe} timeframe period')
    

# Dedicated OM cleanup to run BEFORE/AFTER depending on timeframe boundary

def _is_timeframe_boundary(now_dt: dt, timeframe: str) -> bool:
	try:
		if timeframe.endswith('m'):
			mins = int(timeframe[:-1])
			return (now_dt.minute % mins) == 0
		if timeframe.endswith('h'):
			hours = int(timeframe[:-1])
			return (now_dt.hour % hours) == 0 and now_dt.minute == 0
		if timeframe.endswith('d'):
			return now_dt.hour == 0 and now_dt.minute == 0
	except Exception:
		return False
	return False


def _om_minute_cleanup(mode: str = 'auto'):
	if not (order_manager_enabled and om):
		return
	# Skip/Run depending on boundary and mode
	now_dt = dt.now()
	is_boundary = _is_timeframe_boundary(now_dt, trading_timeframe)
	if mode == 'before' and is_boundary:
		return
	if mode == 'after' and not is_boundary:
		return
	# 'auto' mode runs always
	try:
		# Build symbol set using bulk queries
		symbols: set = set()
		try:
			open_orders = bnc_conn.get_all_open_orders()
			for o in (open_orders or []):
				sym = o.get('symbol') or o.get('symbolName')
				if sym:
					symbols.add(sym)
		except Exception:
			pass
		try:
			pos_syms = bnc_conn.get_nonzero_position_symbols()
			symbols.update(pos_syms)
		except Exception:
			pass
		for sym in symbols:
			try:
				print(f"[OM-CLEAN] symbol={sym} …")
				om.watch_and_cleanup(sym)
			except Exception:
				pass
	except Exception:
		pass

# Local aligned scheduler (no second pairs selection)

def _schedule_aligned(timeframe: str):
	print(f'Waiting for the beginning of the {timeframe} timeframe period...\n')
	# run order calc first (timeframe at :01 where applicable), then OM cleanup at :02, then active deals at :03
	schedule.every().minute.at(":02").do(_om_minute_cleanup, 'auto')
	schedule.every().minute.at(":03").do(main_func, [], True)
	# timeframe triggers at :01 pattern
	if timeframe == "1m":
		schedule.every().minute.at(":01").do(main_func, [], False)
	elif timeframe == "5m":
		schedule.every().hour.at("00:01").do(main_func, [], False)
		schedule.every().hour.at("05:01").do(main_func, [], False)
		schedule.every().hour.at("10:01").do(main_func, [], False)
		schedule.every().hour.at("15:01").do(main_func, [], False)
		schedule.every().hour.at("20:01").do(main_func, [], False)
		schedule.every().hour.at("25:01").do(main_func, [], False)
		schedule.every().hour.at("30:01").do(main_func, [], False)
		schedule.every().hour.at("35:01").do(main_func, [], False)
		schedule.every().hour.at("40:01").do(main_func, [], False)
		schedule.every().hour.at("45:01").do(main_func, [], False)
		schedule.every().hour.at("50:01").do(main_func, [], False)
		schedule.every().hour.at("55:01").do(main_func, [], False)
	elif timeframe == "15m":
		schedule.every().hour.at("00:01").do(main_func, [], False)
		schedule.every().hour.at("15:01").do(main_func, [], False)
		schedule.every().hour.at("30:01").do(main_func, [], False)
		schedule.every().hour.at("45:01").do(main_func, [], False)
	elif timeframe == "1h":
		schedule.every().hour.at("00:01").do(main_func, [], False)
	elif timeframe == "4h":
		schedule.every().day.at("00:00:01").do(main_func, [], False)
		schedule.every().day.at("04:00:01").do(main_func, [], False)
		schedule.every().day.at("08:00:01").do(main_func, [], False)
		schedule.every().day.at("12:00:01").do(main_func, [], False)
		schedule.every().day.at("16:00:01").do(main_func, [], False)
		schedule.every().day.at("20:00:01").do(main_func, [], False)
	elif timeframe == "1d":
		schedule.every().day.at("00:00:01").do(main_func, [], False)
	else:
		print("Invalid time period string")

	while True:
		try:
			schedule.run_pending()
			time.sleep(1)
		except Exception:
			time.sleep(1)

sсheduled_tasks_thread = threading.Thread(target=_schedule_aligned, args=(trading_timeframe,), daemon=True)

if __name__ == '__main__':
    sсheduled_tasks_thread.start()
    bot.infinity_polling()
    # try:
    #     bot.polling(non_stop = True, interval = 0, timeout = 0)
    # except:
    #     pass