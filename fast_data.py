from __future__ import annotations

import threading
import time
from datetime import datetime as dt
from typing import Dict, Tuple, Optional

import pandas as pd
import requests


class FastDataManager:
	"""
	Lightweight high-speed klines fetcher with in-memory caches and persistent HTTP session.
	- Reuses a single requests.Session for keep-alive
	- Maintains per-(pair,timeframe,futures) caches
	- Incremental updates: fetch last 2 klines and shift window on demand
	- Thread-safe via simple lock per key
	"""
	def __init__(self) -> None:
		self.session = requests.Session()
		self.caches: Dict[Tuple[str, str, bool], Dict[str, object]] = {}
		self.locks: Dict[Tuple[str, str, bool], threading.Lock] = {}
		self.ready = False

	def start(self, *, prewarm_pairs: list[str] | None = None, timeframes: list[str] | None = None, basic_candle_depth: Dict[str, int] | None = None, futures: bool = False) -> None:
		self.ready = True
		# Optional prewarm can be implemented later if needed

	def _get_lock(self, key: Tuple[str, str, bool]) -> threading.Lock:
		if key not in self.locks:
			self.locks[key] = threading.Lock()
		return self.locks[key]

	def _response_to_df(self, resp_json) -> pd.DataFrame:
		if not isinstance(resp_json, list):
			return pd.DataFrame(columns=["O_time", "Open", "High", "Low", "Close", "Volume"])
		rows = []
		for item in resp_json:
			if not isinstance(item, list) or len(item) < 6:
				continue
			rows.append(item[0:6])
		return pd.DataFrame(rows, columns=["O_time", "Open", "High", "Low", "Close", "Volume"])

	def _build_urls(self, pair: str, timeframe: str, limit: int, futures: bool) -> Tuple[str, str]:
		if futures:
			base = "https://fapi.binance.com/fapi/v1/klines"
		else:
			base = "https://api.binance.com/api/v3/klines"
		full = f"{base}?symbol={pair}&interval={timeframe}&limit={limit}"
		inc = f"{base}?symbol={pair}&interval={timeframe}&limit=2"
		return full, inc

	def get_series(self, pair: str, timeframe: str, *, limit: int, futures: bool = False) -> pd.DataFrame:
		key = (pair, timeframe, futures)
		lock = self._get_lock(key)
		with lock:
			cap = limit
			if key not in self.caches or cap > int(self.caches[key]['capacity']):
				full_url, _ = self._build_urls(pair, timeframe, limit, futures)
				resp = self.session.get(full_url)
				df = self._response_to_df(resp.json())
				self.caches[key] = { 'df': df, 'capacity': cap }
				return df.copy()
			# incremental
			_, inc_url = self._build_urls(pair, timeframe, 2, futures)
			inc_resp = self.session.get(inc_url)
			inc_df = self._response_to_df(inc_resp.json())
			if inc_df.shape[0] >= 2:
				last_closed = inc_df.iloc[inc_df.shape[0] - 2]
				cached_df = self.caches[key]['df']
				if cached_df.shape[0] == 0 or int(cached_df.iloc[cached_df.shape[0] - 1]['O_time']) != int(last_closed['O_time']):
					self.caches[key]['df'] = pd.concat([cached_df, last_closed.to_frame().T], ignore_index=True)
					if self.caches[key]['df'].shape[0] > cap:
						self.caches[key]['df'] = self.caches[key]['df'].iloc[-cap:].reset_index(drop=True)
			return self.caches[key]['df'].iloc[-cap:].reset_index(drop=True).copy()


# Singleton-ish manager
_manager: Optional[FastDataManager] = None
_use_fast: bool = False


def enable_fast_backend(*, use_fast: bool, prewarm_pairs: list[str] | None = None, timeframes: list[str] | None = None, basic_candle_depth: Dict[str, int] | None = None, futures: bool = False) -> None:
	global _manager, _use_fast
	_use_fast = use_fast
	if not _use_fast:
		return
	if _manager is None:
		_manager = FastDataManager()
	_manager.start(prewarm_pairs=prewarm_pairs, timeframes=timeframes, basic_candle_depth=basic_candle_depth, futures=futures)


def fast_get_ohlcv(pair: str, timeframe: str, *, limit: int, futures: bool = False) -> pd.DataFrame:
	if not _use_fast or _manager is None:
		return pd.DataFrame(columns=["O_time", "Open", "High", "Low", "Close", "Volume"])
	return _manager.get_series(pair, timeframe, limit=limit, futures=futures) 