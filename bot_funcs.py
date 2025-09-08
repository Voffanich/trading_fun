import json
import time
from datetime import datetime as dt

import pandas as pd
import requests
import schedule

import aux_funcs as af
import indicators as ind


# Simple in-memory cache for OHLCV data per (pair, timeframe, futures)
# cache[(pair, timeframe, futures)] = { 'df': DataFrame, 'capacity': int }
_ohlcv_cache = {}

# Daily cache for dynamic trading pairs list
_dynamic_pairs_cache = { 'date': None, 'pairs': [] }

# Daily cache for valid UM futures symbols
_valid_um_usdt_cache = { 'date': None, 'symbols': set() }


def timestamp() -> str:
	return dt.strftime(dt.now(), "%Y-%m-%d %H:%M:%S")


def load_config(config_file_name: str) -> dict:
	with open(config_file_name) as config_file:
		return json.load(config_file)


def get_ohlcv_data_binance(pair: str, timeframe: str, limit: int = 100, futures: bool = False) -> pd.DataFrame:
		
	url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={timeframe}&limit={limit}"	
	url_futures = f"https://fapi.binance.com/fapi/v1/klines?symbol={pair}&interval={timeframe}&limit={limit}"

	key = (pair, timeframe, futures)

	def _response_to_df(resp_json):
		# Expect list[list]; otherwise return empty DataFrame
		if not isinstance(resp_json, list):
			return pd.DataFrame(columns=["O_time", "Open", "High", "Low", "Close", "Volume"])
		ohlcv_data = [] # Only open time, open, high, low, close, volume data from response
		for candle in resp_json:
			if not isinstance(candle, list) or len(candle) < 6:
				continue
			ohlcv = candle[0:6] # Open Time, Open, High, Low, Close, Volume
			ohlcv_data.append(ohlcv)
		return pd.DataFrame(ohlcv_data, columns=["O_time", "Open", "High", "Low", "Close", "Volume"])

	try:
		# If no cache yet or requested a larger window than cached capacity → full backfill
		if key not in _ohlcv_cache or limit > _ohlcv_cache[key]['capacity']:
			if futures:
				response = requests.get(url_futures)
			else:
				response = requests.get(url)
			data = response.json()
			# If Binance returned an error object
			if isinstance(data, dict) and 'code' in data:
				print(f"{timestamp()} - Binance error fetching klines ({pair},{timeframe},{'futures' if futures else 'spot'}): {data}")
				return pd.DataFrame(columns=["O_time", "Open", "High", "Low", "Close", "Volume"])
			df_full = _response_to_df(data)
			_ohlcv_cache[key] = { 'df': df_full, 'capacity': limit }
			# Return a copy to avoid external mutation of cached frame
			return _ohlcv_cache[key]['df'].copy()

		# Incremental update path: fetch just the latest 2 candles (to get last closed)
		inc_url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={timeframe}&limit=2"
		inc_url_futures = f"https://fapi.binance.com/fapi/v1/klines?symbol={pair}&interval={timeframe}&limit=2"
		if futures:
			inc_resp = requests.get(inc_url_futures)
		else:
			inc_resp = requests.get(inc_url)
		inc_data = inc_resp.json()
		if isinstance(inc_data, dict) and 'code' in inc_data:
			print(f"{timestamp()} - Binance error fetching inc klines ({pair},{timeframe},{'futures' if futures else 'spot'}): {inc_data}")
			# Return current cache tail
			cap = _ohlcv_cache[key]['capacity']
			need = min(limit, cap)
			return _ohlcv_cache[key]['df'].iloc[-need:].reset_index(drop=True).copy()
		inc_df = _response_to_df(inc_data)

		# Last closed candle is the penultimate (index -2) in Binance klines responses
		if inc_df.shape[0] >= 2:
			last_closed = inc_df.iloc[inc_df.shape[0] - 2]
			cached_df = _ohlcv_cache[key]['df']
			if cached_df.shape[0] == 0 or int(cached_df.iloc[cached_df.shape[0] - 1]['O_time']) != int(last_closed['O_time']):
				# Append new closed candle
				_ohlcv_cache[key]['df'] = pd.concat([cached_df, last_closed.to_frame().T], ignore_index=True)
				# Trim to capacity (keep the most recent rows)
				cap = _ohlcv_cache[key]['capacity']
				if _ohlcv_cache[key]['df'].shape[0] > cap:
					_ohlcv_cache[key]['df'] = _ohlcv_cache[key]['df'].iloc[-cap:].reset_index(drop=True)
		# Return the tail matching the requested limit (<= capacity)
		cap = _ohlcv_cache[key]['capacity']
		need = min(limit, cap)
		return _ohlcv_cache[key]['df'].iloc[-need:].reset_index(drop=True).copy()

	except ConnectionError as error:
		print(f'{timestamp()} - Connection error: ', error)
	except Exception as ex:
		print(f'{timestamp()} - Some another error with getting the responce from Binance')
		print(ex)
		# Fallback: try a full fetch if cache path failed
		try:
			if futures:
				response = requests.get(url_futures)
			else:
				response = requests.get(url)
			data = response.json()
			if isinstance(data, dict) and 'code' in data:
				print(f"{timestamp()} - Binance error on fallback klines ({pair},{timeframe},{'futures' if futures else 'spot'}): {data}")
				return pd.DataFrame(columns=["O_time", "Open", "High", "Low", "Close", "Volume"])
			df_full = _response_to_df(data)
			_ohlcv_cache[key] = { 'df': df_full, 'capacity': limit }
			return _ohlcv_cache[key]['df'].copy()
		except Exception as ex2:
			print(f'{timestamp()} - Secondary fetch failed')
			print(ex2)
			# Last resort: return what we may have in cache
			if key in _ohlcv_cache and _ohlcv_cache[key]['df'].shape[0] > 0:
				cap = _ohlcv_cache[key]['capacity']
				need = min(limit, cap)
				return _ohlcv_cache[key]['df'].iloc[-need:].reset_index(drop=True).copy()
			return pd.DataFrame(columns=["O_time", "Open", "High", "Low", "Close", "Volume"]) 


# -------- Dynamic trading pairs (daily top-N by volume) --------

def _get_valid_um_usdt_symbols() -> set[str]:
	current_date = dt.utcnow().date()
	if _valid_um_usdt_cache['date'] == current_date and _valid_um_usdt_cache['symbols']:
		return _valid_um_usdt_cache['symbols']
	try:
		info_url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
		resp = requests.get(info_url)
		data = resp.json()
		symbols = set()
		for sym in data.get('symbols', []):
			if sym.get('contractType') == 'PERPETUAL' and sym.get('quoteAsset') == 'USDT' and sym.get('status') == 'TRADING':
				symbols.add(sym.get('symbol'))
		_valid_um_usdt_cache['date'] = current_date
		_valid_um_usdt_cache['symbols'] = symbols
		return symbols
	except Exception as ex:
		print(f"{timestamp()} - Failed to fetch exchangeInfo: {ex}")
		return _valid_um_usdt_cache['symbols'] or set()


def fetch_top_usdt_futures_pairs(top_n: int) -> list[str]:
	"""
	Получает топ-N USDT-M фьючерсных пар по 24h объему с Binance Futures.
	Возвращает список символов, например ["BTCUSDT", "ETHUSDT", ...]
	"""
	try:
		url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
		resp = requests.get(url)
		data = resp.json()
		valid = _get_valid_um_usdt_symbols()
		# фильтруем только валидные *USDT UM perpetual
		usdt = [item for item in data if isinstance(item, dict) and item.get('symbol') in valid]
		# сортировка по объему quoteVolume (в USDT)
		for item in usdt:
			# безопасное преобразование quoteVolume
			try:
				item['_quoteVolume'] = float(item.get('quoteVolume', 0.0))
			except Exception:
				item['_quoteVolume'] = 0.0
		usdt_sorted = sorted(usdt, key=lambda x: x.get('_quoteVolume', 0.0), reverse=True)
		pairs = [x['symbol'] for x in usdt_sorted[:top_n]]
		return pairs
	except Exception as ex:
		print(f"{timestamp()} - Failed to fetch top futures pairs: {ex}")
		return []


def _fetch_filters_map() -> dict:
	"""
	Возвращает карту символ -> (tickSize, stepSize, minQty, minNotional)
	"""
	try:
		info_url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
		resp = requests.get(info_url)
		data = resp.json()
		result = {}
		for sym in data.get('symbols', []):
			if sym.get('contractType') == 'PERPETUAL' and sym.get('quoteAsset') == 'USDT' and sym.get('status') == 'TRADING':
				filters = {f.get('filterType'): f for f in sym.get('filters', [])}
				tick = float(filters.get('PRICE_FILTER', {}).get('tickSize', 0) or 0)
				step = float(filters.get('LOT_SIZE', {}).get('stepSize', 0) or 0)
				min_qty = float(filters.get('LOT_SIZE', {}).get('minQty', 0) or 0)
				mn = filters.get('MIN_NOTIONAL', {})
				min_notional = float(mn.get('notional', mn.get('minNotional', 0)) or 0)
				result[sym.get('symbol')] = (tick, step, min_qty, min_notional)
		return result
	except Exception as ex:
		print(f"{timestamp()} - Failed to fetch filters map: {ex}")
		return {}


def _fetch_prices_map(symbols: list[str]) -> dict:
	"""
	Возвращает карту symbol -> price (last) для списка символов.
	"""
	result = {}
	try:
		url = "https://fapi.binance.com/fapi/v1/ticker/price"
		resp = requests.get(url)
		data = resp.json()
		wanted = set(symbols)
		for item in data:
			if isinstance(item, dict):
				sym = item.get('symbol')
				if sym in wanted:
					try:
						result[sym] = float(item.get('price', 0))
					except Exception:
						result[sym] = 0.0
		return result
	except Exception as ex:
		print(f"{timestamp()} - Failed to fetch prices: {ex}")
		return result


def filter_pairs_by_min_notional(pairs: list[str], *, bank_usdt: float, risk_percent: float, min_stop_perc: float, safety_buffer_perc: float = 2.0, verbose: bool = False) -> list[str]:
	"""
	Фильтрует пары, оставляя только те, где при минимальной дистанции стопа
	и заданном риске исполнится биржевой minNotional после округлений.
	- min_stop_perc будет умножен на 1.25 (смягчение условий по ТЗ)
	- Дополнительно добавляется небольшой safety buffer к minNotional (по умолчанию 2%)
	"""
	if bank_usdt <= 0 or risk_percent <= 0 or min_stop_perc <= 0:
		if verbose:
			print(f"{timestamp()} - MinNotional filter skipped: bank_usdt={bank_usdt}, risk_percent={risk_percent}, min_stop_perc={min_stop_perc}")
		return []
	filters_map = _fetch_filters_map()
	prices_map = _fetch_prices_map(pairs)
	result = []
	adj_min_stop_perc = min_stop_perc * 1.25
	if verbose:
		print(f"{timestamp()} - MinNotional filter start: pairs={len(pairs)}, bank_usdt={bank_usdt}, risk_percent={risk_percent}, min_stop_perc={min_stop_perc} -> adj={adj_min_stop_perc}, safety_buffer_perc={safety_buffer_perc}")
	for sym in pairs:
		if sym not in filters_map or sym not in prices_map:
			if verbose:
				print(f"  {sym}: skipped (no filters or price)")
			continue
		price = float(prices_map.get(sym, 0.0))
		if price <= 0:
			if verbose:
				print(f"  {sym}: skipped (price<=0)")
			continue
		tick, step, min_qty, min_notional = filters_map[sym]
		# минимальная дистанция до стопа в абсолюте
		delta_abs = price * (adj_min_stop_perc / 100.0)
		if delta_abs <= 0:
			if verbose:
				print(f"  {sym}: skipped (delta_abs<=0)")
			continue
		risk_amount = bank_usdt * (risk_percent / 100.0)
		qty_raw = risk_amount / delta_abs
		# округление вниз к шагу лота
		if step > 0:
			qty_steps = int(qty_raw / step)
			qty_rounded = qty_steps * step
		else:
			qty_rounded = qty_raw
		reason = None
		passed = True
		if qty_rounded < min_qty or qty_rounded <= 0:
			passed = False
			reason = f"qty({qty_rounded})<minQty({min_qty})"
		notional = price * qty_rounded
		min_notional_with_buffer = min_notional * (1.0 + safety_buffer_perc / 100.0) if min_notional > 0 else 0
		if passed and min_notional_with_buffer > 0 and notional < min_notional_with_buffer:
			passed = False
			reason = f"notional({af.r_signif(notional, 4)})<minNotional({min_notional_with_buffer})"
		if verbose:
			print(
				f"  {sym}: price={af.r_signif(price, 4)}, step={step}, minQty={min_qty}, minNotional={min_notional}, "
				f"delta_abs={af.r_signif(delta_abs, 4)}, risk_amount={af.r_signif(risk_amount, 4)}, qty_raw={qty_raw}, qty_rounded={qty_rounded}, "
				f"notional={af.r_signif(notional, 4)} -> {'PASS' if passed else 'FAIL'}{(' ('+reason+')') if reason else ''}"
			)
		if passed:
			result.append(sym)
	return result


def get_daily_dynamic_pairs(top_n: int) -> list[str]:
	"""
	Возвращает кэшированный на сутки список пар. Обновляет кэш при смене даты.
	"""
	current_date = dt.utcnow().date()
	if _dynamic_pairs_cache['date'] != current_date:
		pairs = fetch_top_usdt_futures_pairs(top_n)
		_dynamic_pairs_cache['date'] = current_date
		_dynamic_pairs_cache['pairs'] = pairs
	return list(_dynamic_pairs_cache['pairs'])


def get_daily_dynamic_pairs_filtered(config: dict) -> list[str]:
	"""
	Возвращает кэшированный на сутки список пар, дополнительно отфильтрованный по minNotional
	с учётом банка, риска и минимальной дистанции стопа из конфига.
	"""
	current_date = dt.utcnow().date()
	if _dynamic_pairs_cache['date'] != current_date:
		pairs = fetch_top_usdt_futures_pairs(int(config['general']['dynamic_trading_pairs_top_n']))
		# параметры фильтра
		bank_usdt = float(
			config['general'].get('dynamic_pairs_bank',
				config['general'].get('initial_bank_for_test_stats', 0)
			)
		)
		risk_percent = float(config['deal_config'].get('deal_risk_perc_of_bank', 0))
		min_stop_perc = float(config['deal_config'].get('stop_distance_threshold', 0))
		verbose = bool(config['general'].get('enable_trade_calc_logging', False))
		filtered = filter_pairs_by_min_notional(
			pairs,
			bank_usdt=bank_usdt,
			risk_percent=risk_percent,
			min_stop_perc=min_stop_perc,
			safety_buffer_perc=2.0,
			verbose=verbose,
		)
		_dynamic_pairs_cache['date'] = current_date
		_dynamic_pairs_cache['pairs'] = filtered
		if verbose:
			print(f"{timestamp()} - Daily dynamic pairs selected: {len(filtered)}")
			print(f"  Pairs: {', '.join(filtered) if filtered else '[]'}")
	return list(_dynamic_pairs_cache['pairs'])


def define_checked_timeframes(used_timeframes: list, timeframe: str) -> list:
	del used_timeframes[0:used_timeframes.index(timeframe)]
	return used_timeframes


def set_schedule(timeframe: str, task, trading_pairs: list):
	print(f'Waiting for the beginning of the {timeframe} timeframe period...\n')
	# initial info for static pairs (no immediate task run)
	try:
		print(f"{timestamp()} - Using static pairs: {len(trading_pairs)}")
		print(f"  Pairs: {', '.join(trading_pairs) if trading_pairs else '[]'}")
	except Exception as ex:
		print(f"{timestamp()} - Failed to print static pairs: {ex}")
	
	#running every minute tasks
		
	schedule.every().minute.at(":02").do(task, trading_pairs, True)
	   
	if timeframe == "1m":
		schedule.every().minute.at(":01").do(task, trading_pairs, False)
	elif timeframe == "5m":
		schedule.every().hour.at("00:01").do(task, trading_pairs, False)
		schedule.every().hour.at("05:01").do(task, trading_pairs, False)
		schedule.every().hour.at("10:01").do(task, trading_pairs, False)
		schedule.every().hour.at("15:01").do(task, trading_pairs, False)
		schedule.every().hour.at("25:01").do(task, trading_pairs, False)
		schedule.every().hour.at("20:01").do(task, trading_pairs, False)
		schedule.every().hour.at("30:01").do(task, trading_pairs, False)
		schedule.every().hour.at("35:01").do(task, trading_pairs, False)
		schedule.every().hour.at("40:01").do(task, trading_pairs, False)
		schedule.every().hour.at("45:01").do(task, trading_pairs, False)
		schedule.every().hour.at("50:01").do(task, trading_pairs, False)
		schedule.every().hour.at("55:01").do(task, trading_pairs, False) 
	elif timeframe == "15m":
		schedule.every().hour.at("00:01").do(task, trading_pairs, False)
		schedule.every().hour.at("15:01").do(task, trading_pairs, False)
		schedule.every().hour.at("30:01").do(task, trading_pairs, False)
		schedule.every().hour.at("45:01").do(task, trading_pairs, False)
	elif timeframe == "1h":
		schedule.every().hour.at("00:01").do(task, trading_pairs, False)
	elif timeframe == "4h":
		schedule.every().day.at("00:00:01").do(task, trading_pairs, False)
		schedule.every().day.at("04:00:01").do(task, trading_pairs, False)
		schedule.every().day.at("08:00:01").do(task, trading_pairs, False)
		schedule.every().day.at("12:00:01").do(task, trading_pairs, False)
		schedule.every().day.at("16:00:01").do(task, trading_pairs, False)
		schedule.every().day.at("20:00:01").do(task, trading_pairs, False)
	elif timeframe == "1d":
		schedule.every().day.at("00:00:01").do(task, trading_pairs, False)
	else:
		print("Invalid time period string")
	
	while True:
		try:
			schedule.run_pending()
			time.sleep(1)
		except Exception:
			print(Exception)


def set_schedule_dynamic(timeframe: str, task, config: dict):
	"""
	Планировщик с выбором списка пар по флагу в конфиге.
	- Если general.use_dynamic_trading_pairs = True → ежедневно берём top-N UM USDT perpetual по объёму
		и фильтруем по minNotional/риску/минимальному стопу
	- Иначе → используем статический список из config['general']['trading_pairs']
	"""
	print(f'Waiting for the beginning of the {timeframe} timeframe period...\n')
	
	top_n = config['general']['dynamic_trading_pairs_top_n']
	use_dynamic = bool(config['general'].get('use_dynamic_trading_pairs'))

	def _task_wrapper(minute_flag: bool):
		if use_dynamic:
			pairs = get_daily_dynamic_pairs_filtered(config)
		else:
			pairs = config['general']['trading_pairs']
		return task(pairs, minute_flag)

	# running every minute tasks
	schedule.every().minute.at(":02").do(_task_wrapper, True)

	if timeframe == "1m":
		schedule.every().minute.at(":01").do(_task_wrapper, False)
	elif timeframe == "5m":
		schedule.every().hour.at("00:01").do(_task_wrapper, False)
		schedule.every().hour.at("05:01").do(_task_wrapper, False)
		schedule.every().hour.at("10:01").do(_task_wrapper, False)
		schedule.every().hour.at("15:01").do(_task_wrapper, False)
		schedule.every().hour.at("25:01").do(_task_wrapper, False)
		schedule.every().hour.at("20:01").do(_task_wrapper, False)
		schedule.every().hour.at("30:01").do(_task_wrapper, False)
		schedule.every().hour.at("35:01").do(_task_wrapper, False)
		schedule.every().hour.at("40:01").do(_task_wrapper, False)
		schedule.every().hour.at("45:01").do(_task_wrapper, False)
		schedule.every().hour.at("50:01").do(_task_wrapper, False)
		schedule.every().hour.at("55:01").do(_task_wrapper, False)
	elif timeframe == "15m":
		schedule.every().hour.at("00:01").do(_task_wrapper, False)
		schedule.every().hour.at("15:01").do(_task_wrapper, False)
		schedule.every().hour.at("30:01").do(_task_wrapper, False)
		schedule.every().hour.at("45:01").do(_task_wrapper, False)
	elif timeframe == "1h":
		schedule.every().hour.at("00:01").do(_task_wrapper, False)
	elif timeframe == "4h":
		schedule.every().day.at("00:00:01").do(_task_wrapper, False)
		schedule.every().day.at("04:00:01").do(_task_wrapper, False)
		schedule.every().day.at("08:00:01").do(_task_wrapper, False)
		schedule.every().day.at("12:00:01").do(_task_wrapper, False)
		schedule.every().day.at("16:00:01").do(_task_wrapper, False)
		schedule.every().day.at("20:00:01").do(_task_wrapper, False)
	elif timeframe == "1d":
		schedule.every().day.at("00:00:01").do(_task_wrapper, False)
	else:
		print("Invalid time period string")

	# initial pairs selection only (no task run) so logs appear but we wait for the first schedule
	try:
		if use_dynamic:
			pairs = get_daily_dynamic_pairs_filtered(config)
			if bool(config['general'].get('enable_trade_calc_logging', False)):
				print(f"{timestamp()} - Initial dynamic pairs selected: {len(pairs)}")
				print(f"  Pairs: {', '.join(pairs) if pairs else '[]'}")
		else:
			pairs = config['general']['trading_pairs']
			print(f"{timestamp()} - Using static pairs: {len(pairs)}")
			print(f"  Pairs: {', '.join(pairs) if pairs else '[]'}")
	except Exception as ex:
		print(f"{timestamp()} - Initial pairs selection failed: {ex}")

	while True:
		try:
			schedule.run_pending()
			time.sleep(1)
		except Exception:
			print(Exception)


def update_current_deal_price(db, deal: object, current_price: float):
	
	if deal.direction == 'long':
		current_price_perc = round((current_price - deal.entry_price) / deal.entry_price * 100, 2)
	elif deal.direction == 'short':
		current_price_perc = round((current_price - deal.entry_price) / deal.entry_price * 100, 2) * -1
		
	
	db.update_deal_data('current_price', current_price, deal.deal_id)
	db.update_deal_data('current_price_perc', current_price_perc, deal.deal_id)
	
def update_best_price(db, deal: object, best_price: float):
	
	best_price_perc = abs(round((best_price - deal.entry_price) / deal.entry_price * 100, 2))
	
	db.update_deal_data('best_price', af.r_signif(best_price, 4), deal.deal_id)
	db.update_deal_data('best_price_perc', best_price_perc, deal.deal_id)


def update_worst_price(db, deal: object, worst_price: float):
	
	worst_price_perc = abs(round((worst_price - deal.entry_price) / deal.entry_price * 100, 2))
	
	db.update_deal_data('worst_price', af.r_signif(worst_price, 4), deal.deal_id)
	db.update_deal_data('worst_price_perc', worst_price_perc, deal.deal_id)


def update_active_deals(db: object, cd: object, bot: object, chat_id: int, active_deals: list[object], last_candle: object, reverse: bool = True):
	
	last_candle_high = af.r_signif(float(last_candle.High), 4)
	last_candle_low = af.r_signif(float(last_candle.Low), 4)
	last_cande_close = af.r_signif(float(last_candle.Close), 4)
	
	for deal in active_deals:
		
		update_current_deal_price(db, deal, last_cande_close)
		
		if deal.direction == 'long':
			
			if last_candle_high > deal.take_price:
				db.update_deal_data('status', 'win', deal.deal_id)
				db.update_deal_data('finish_time', timestamp(), deal.deal_id)
				update_best_price(db, deal, last_candle_high)
        
				if last_candle_low < deal.worst_price:
					update_worst_price(db, deal, last_candle_low)					
					
				send_win_message(bot, chat_id, deal)
				print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Won')
				
				if reverse:
					cd.add_lost_deal(bot, chat_id)
				
			elif last_candle_low < deal.stop_price:
				db.update_deal_data('status', 'loss', deal.deal_id)
				db.update_deal_data('finish_time', timestamp(), deal.deal_id)
				update_worst_price(db, deal, last_candle_low) 
				if last_candle_high > deal.best_price:
					update_best_price(db, deal, last_candle_high)
				
				send_loss_message(bot, chat_id, deal)
				print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Lost')
				
				if not reverse:
					cd.add_lost_deal(bot, chat_id)
				
			elif last_candle_high > deal.best_price:
				update_best_price(db, deal, last_candle_high)
				print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Best price updated')
								
			elif last_candle_low < deal.worst_price:
				update_worst_price(db, deal, last_candle_low) 
				print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Worst price updated')
							  
		elif deal.direction == 'short':
			
			if last_candle_low < deal.take_price:
				db.update_deal_data('status', 'win', deal.deal_id)
				db.update_deal_data('finish_time', timestamp(), deal.deal_id)
				update_best_price(db, deal, last_candle_low)
				
				if last_candle_high > deal.worst_price:
					update_worst_price(db, deal, last_candle_high) 
				
				send_win_message(bot, chat_id, deal)
				print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Won')
				
				if reverse:
					cd.add_lost_deal(bot, chat_id)
				
			elif last_candle_high > deal.stop_price:
				db.update_deal_data('status', 'loss', deal.deal_id)
				db.update_deal_data('finish_time', timestamp(), deal.deal_id)
				update_worst_price(db, deal, last_candle_high)
				if last_candle_low < deal.best_price:
					update_best_price(db, deal, last_candle_low)
								
				send_loss_message(bot, chat_id, deal)
				print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Lost')
				
				if not reverse:
					cd.add_lost_deal(bot, chat_id)
				
			elif last_candle_low < deal.best_price:
				update_best_price(db, deal, last_candle_low)
				print(f'Deal id {deal.deal_id}, {deal.pair}, {deal.direction} - Best price updated')
								
			elif last_candle_high > deal.worst_price:
				update_worst_price(db, deal, last_candle_high)
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
	Лучшая позиция: {deal.best_price_perc}%
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
	Лучшая позиция: {deal.best_price_perc}%
	Дистанция до стопа: {deal.stop_dist_perc}%
	"""
	
	bot.send_message(chat_id, text=message, parse_mode = 'HTML')
		
		

def check_active_deals(db, cd, bot, chat_id, reverse):
	
	active_deal_pairs = db.get_active_deals_list()
	# print(f'{active_deal_pairs=}')
	
	
	for pair in active_deal_pairs:
		try:
			df = get_ohlcv_data_binance(pair, '1m', limit=2, futures=True)
			if df is None or df.shape[0] < 2:
				print(f"{timestamp()} - Not enough klines for active deals check: {pair}")
				continue
			last_candle = (df.iloc[df.shape[0] - 2])	   # OHLCV data of the last closed candle as object
			
			# get active deals from database    
			active_deals = db.read_active_deals(pair)
			#check and update active deals for result or best/worst price
			update_active_deals(db, cd, bot, chat_id, active_deals, last_candle, reverse=reverse)  
		except Exception as ex:
			print(f'{timestamp()} - Some fucking error happened')
			print(ex)
			continue
	

def validate_deal(db: object, deal: object, deal_config: dict, basic_tf_ohlvc_df: pd.DataFrame, validate_on: bool = False):
			
	if validate_on:
		max_one_direction_deals = deal_config['max_one_direction_deals']
		direction_quantity_diff = deal_config['direction_quantity_diff']
		max_deals_total = deal_config['max_deals_total']
		max_deals_pair = deal_config['max_deals_pair']
		
		total_active_deals_quantity = db.total_active_deals_quantity()
		pair_active_deals_quantity = db.pair_active_deals_quantity(deal.pair)
		active_shorts_quantity = db.active_shorts_quantity()
		active_longs_quantity = db.active_longs_quantity()
		
		if total_active_deals_quantity >= max_deals_total:
			print(f'-- Active deals quantity ({total_active_deals_quantity}) already at maximum ({max_deals_total}))')
			return False
		elif pair_active_deals_quantity >= max_deals_pair:
			print(f'-- {deal.pair} active deals quantity ({pair_active_deals_quantity}) already at maximum ({max_deals_pair})')
			return False
		# elif active_shorts_quantity >= max_one_direction_deals + direction_quantity_diff  or active_longs_quantity >= max_one_direction_deals + direction_quantity_diff:
		elif active_shorts_quantity >= max_one_direction_deals  or active_longs_quantity >= max_one_direction_deals:
			if active_shorts_quantity - active_longs_quantity >= direction_quantity_diff and deal.direction == 'short':
				print(f'-- Short deal can\'t be placed. Active shorts - {active_shorts_quantity}, active longs - {active_longs_quantity}, diff - {direction_quantity_diff}')
				return False
			elif active_longs_quantity - active_shorts_quantity >= direction_quantity_diff and deal.direction == 'long':
				print(f'-- Long deal can\'t be placed. Active shorts - {active_shorts_quantity}, active longs - {active_longs_quantity}, diff - {direction_quantity_diff}')
				return False
		
	if deal_config['indicators_validation']:
		return validate_indicators(deal, deal_config, basic_tf_ohlvc_df) 
	else:
		return True
		


def validate_indicators(deal: object, deal_config: dict, basic_tf_ohlvc_df: pd.DataFrame):
	
	indicators_target = deal_config['indicators']
	
	if deal.direction == 'long':
		
		print('entering long rsi check')
		
		print(indicators_target['RSI_long'])
		
		rsi_target = indicators_target['RSI_long']
		rsi = ind.RSI(basic_tf_ohlvc_df)
		
		print(f'{rsi=}, {rsi_target=}')
		
		if rsi_target and rsi < rsi_target:
			print(f'RSI = {rsi} < target RSI = {rsi_target}, deal is approved')
			deal.indicators = deal.indicators + f'RSI:{rsi};'
			print(f'{deal.indicators=}')
			return True
		elif rsi_target and rsi > rsi_target: 
			print(f'RSI = {rsi} > target RSI = {rsi_target}, deal is not approved')
			return False
		else:
			print('Long ELSE!!')
			return True
		
	elif deal.direction == 'short':
		
		print('entering short rsi check')        
		
		rsi_target = indicators_target['RSI_short']
		rsi = ind.RSI(basic_tf_ohlvc_df)
		
		print(f'{rsi=}, {rsi_target=}')
		
		if rsi_target and rsi > rsi_target:
			print(f'RSI = {rsi} > target RSI = {rsi_target}, deal is approved')
			deal.indicators = deal.indicators + f'RSI:{rsi};'
			print(f'{deal.indicators=}')
			return True
		elif rsi_target and rsi < rsi_target: 
			print(f'RSI = {rsi} < target RSI = {rsi_target}, deal is not approved')
			return False
		else:
			print('Short ELSE!!')    
			return True
		
