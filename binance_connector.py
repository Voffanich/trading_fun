from __future__ import annotations

import time
import hmac
import hashlib
from urllib.parse import urlencode, quote
import requests
import json
from typing import Optional, Dict, Any, Tuple, List, Set
from decimal import Decimal, ROUND_DOWN, getcontext

try:
	from binance.um_futures import UMFutures
	from binance.error import ClientError
except Exception:
	UMFutures = None  # type: ignore
	ClientError = Exception  # type: ignore


class BaseFuturesConnector:
	"""Abstract base for Futures connectors (IM classic vs PM).
	Defines common helpers and the public interface that OrderManager consumes.
	"""

	def __init__(self, *, api_key: str, api_secret: str, testnet: bool = False, recv_window_ms: int = 60000, log: bool = True) -> None:
		self.api_key = api_key
		self.api_secret = api_secret
		self.recv_window_ms = recv_window_ms
		self.log_enabled = log
		self._http = requests.Session()
		# cache for symbol info/filters to avoid repeated heavy calls
		self._symbol_info_cache: Dict[str, Dict[str, Any]] = {}
		self._symbol_info_cache_ts: float = 0.0
		self._symbol_info_cache_ttl_sec: int = 3600

	def _log(self, *args: Any) -> None:
		if self.log_enabled:
			try:
				print(" ".join(str(a) for a in args))
			except Exception:
				pass

	def _log_req(self, tag: str, path: str, params: Dict[str, Any]) -> None:
		if not self.log_enabled:
			return
		keys = ("symbol", "side", "type", "orderType", "strategyType", "price", "stopPrice", "activationPrice", "callbackRate", "quantity")
		short = {k: v for k, v in params.items() if k in keys and v is not None}
		self._log(f"[{tag}] {path}", json.dumps(short, ensure_ascii=False))

	def _log_resp(self, tag: str, status: int, body: Any) -> None:
		if not self.log_enabled:
			return
		try:
			brief = body if isinstance(body, dict) else {}
			keep = {}
			for k in ("code", "msg", "orderId", "strategyId", "status", "type", "orderType", "strategyType", "price", "stopPrice", "activationPrice", "callbackRate", "origQty", "executedQty"):
				if isinstance(brief, dict) and k in brief:
					keep[k] = brief[k]
			self._log(f"[{tag}] status={status}", json.dumps(keep, ensure_ascii=False))
		except Exception:
			pass

	# --- Interface (to be implemented/overridden) ---
	def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
		raise NotImplementedError

	def _get_symbol_info_cached(self, symbol: str, fetcher) -> Dict[str, Any]:
		# simple time-based cache for symbol metadata
		now = time.time()
		if (now - self._symbol_info_cache_ts) > self._symbol_info_cache_ttl_sec:
			self._symbol_info_cache.clear()
			self._symbol_info_cache_ts = now
		info = self._symbol_info_cache.get(symbol)
		if info is not None:
			return info
		fetched = fetcher()
		self._symbol_info_cache[symbol] = fetched
		return fetched

	def get_filters(self, symbol: str) -> Dict[str, Dict[str, Any]]:
		info = self.get_symbol_info(symbol)
		filters: Dict[str, Dict[str, Any]] = {}
		for f in info.get("filters", []):
			filters[f.get("filterType")] = f
		return filters

	def _format_by_step(self, value: float, step_str: str) -> str:
		getcontext().prec = 28
		quant = Decimal(step_str or "1")
		q = (Decimal(str(value))).quantize(quant, rounding=ROUND_DOWN)
		s = format(q, 'f')
		if '.' in s:
			s = s.rstrip('0').rstrip('.') or '0'
		return s

	def _tick_size(self, filters: Dict[str, Dict[str, Any]]) -> float:
		pf = filters.get("PRICE_FILTER", {})
		return float(pf.get("tickSize", 0) or 0)

	def _step_size(self, filters: Dict[str, Dict[str, Any]]) -> float:
		ls = filters.get("LOT_SIZE", {})
		return float(ls.get("stepSize", 0) or 0)

	def _min_qty(self, filters: Dict[str, Dict[str, Any]]) -> float:
		ls = filters.get("LOT_SIZE", {})
		return float(ls.get("minQty", 0) or 0)

	def _min_notional(self, filters: Dict[str, Dict[str, Any]]) -> float:
		mn = filters.get("MIN_NOTIONAL", {})
		return float(mn.get("notional", mn.get("minNotional", 0)) or 0)

	def round_price(self, symbol: str, price: float) -> str:
		filters = self.get_filters(symbol)
		tick = self._tick_size(filters)
		return self._format_by_step(price, str(tick or "1"))

	def round_qty(self, symbol: str, qty: float) -> str:
		filters = self.get_filters(symbol)
		step = self._step_size(filters)
		min_q = self._min_qty(filters)
		q = max((Decimal(str(qty)) // Decimal(str(step or 1))) * Decimal(str(step or 1)), Decimal(str(min_q or 0)))
		s = format(q, 'f')
		if '.' in s:
			s = s.rstrip('0').rstrip('.') or '0'
		return s

	def validate_qty_notional(self, symbol: str, price: float, qty: float) -> None:
		filters = self.get_filters(symbol)
		min_q = self._min_qty(filters)
		min_notional = self._min_notional(filters)
		if qty < min_q:
			self._log("[QTY] invalid", json.dumps({"symbol": symbol, "qty": qty, "minQty": min_q}, ensure_ascii=False))
			raise ValueError(f"Quantity {qty} < minQty {min_q}")
		notional = price * qty
		if min_notional > 0 and notional < min_notional:
			self._log("[NOTIONAL] invalid", json.dumps({"symbol": symbol, "price": price, "qty": qty, "notional": notional, "minNotional": min_notional}, ensure_ascii=False))
			raise ValueError(f"Notional {notional} < minNotional {min_notional}")

	# --- Public interface for OrderManager ---
	def get_mark_price(self, symbol: str) -> Optional[float]:
		raise NotImplementedError

	def get_open_orders(self, symbol: str) -> list:
		raise NotImplementedError

	def get_all_open_orders(self) -> List[dict]:
		raise NotImplementedError

	def get_nonzero_position_symbols(self) -> Set[str]:
		raise NotImplementedError

	def get_position(self, symbol: str) -> Optional[dict]:
		raise NotImplementedError

	def cancel_order(self, symbol: str, *, order_id: Optional[Any] = None, client_order_id: Optional[str] = None) -> bool:  # type: ignore
		raise NotImplementedError

	def cancel_all_open_orders(self, symbol: str) -> bool:
		raise NotImplementedError

	def get_usdt_balance(self, balance_type: str = "available") -> float:
		raise NotImplementedError

	def set_margin_type(self, symbol: str, margin_type: str) -> None:
		return None

	def set_leverage(self, symbol: str, leverage: int) -> None:
		return None

	# Placement helpers to be implemented per connector
	def place_limit_entry(self, symbol: str, side: str, price: str, qty: str, tif: str, position_side: str) -> dict:
		raise NotImplementedError

	def place_stop_loss(self, symbol: str, side: str, stop_price: str, qty: str, position_side: str, reduce_only: bool, working_type: str, mode: str = 'auto') -> dict:
		raise NotImplementedError

	def place_take_profit(self, symbol: str, side: str, stop_price: str, qty: str, position_side: str, reduce_only: bool, working_type: str, mode: str = 'auto') -> dict:
		raise NotImplementedError

	def place_trailing(self, symbol: str, side: str, activation_price: str, callback_rate: str, qty: str, position_side: str, reduce_only: bool, working_type: str, mode: str = 'auto') -> dict:
		raise NotImplementedError

	def compute_quantity_by_risk(self, symbol: str, entry_price: float, stop_loss_price: float, risk_percent: float, balance_type: str = "collateral") -> float:
		filters = self.get_filters(symbol)
		step = self._step_size(filters)
		min_q = self._min_qty(filters)
		delta = abs(entry_price - stop_loss_price)
		if delta <= 0:
			raise ValueError("entry and stop must differ")
		bank = self.get_usdt_balance(balance_type)
		self._log("[QTY] inputs", json.dumps({
			"symbol": symbol,
			"balance_type": balance_type,
			"bank": bank,
			"risk_percent": risk_percent,
			"entry_price": entry_price,
			"stop_loss_price": stop_loss_price,
			"delta": delta
		}, ensure_ascii=False))
		if bank is None or float(bank) <= 0:
			raise ValueError("bank is zero for quantity calculation")
		risk_amount = bank * (risk_percent / 100.0)
		qty_raw = risk_amount / delta
		# round
		q_str = self.round_qty(symbol, float(qty_raw))
		q = float(q_str)
		self._log("[QTY] calc", json.dumps({
			"risk_amount": risk_amount,
			"qty_raw": qty_raw,
			"qty_rounded": q
		}, ensure_ascii=False))
		if q < min_q:
			raise ValueError("Calculated qty below minQty")
		return q


class ClassicIMConnector(BaseFuturesConnector):
	"""UM Futures classic connector (Isolated/Cross, но не PM)."""

	def __init__(self, *, api_key: str, api_secret: str, testnet: bool = False, recv_window_ms: int = 60000, log: bool = True, base_url: Optional[str] = None) -> None:
		super().__init__(api_key=api_key, api_secret=api_secret, testnet=testnet, recv_window_ms=recv_window_ms, log=log)
		if UMFutures is None:
			raise RuntimeError("python-binance UMFutures not available")
		if testnet:
			self.client = UMFutures(key=api_key, secret=api_secret, base_url=base_url or "https://testnet.binancefuture.com")
		else:
			self.client = UMFutures(key=api_key, secret=api_secret, base_url=base_url or None)

	# Metadata
	def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
		def _fetch():
			info = self.client.exchange_info()
			for s in info.get("symbols", []):
				if s.get("symbol") == symbol:
					return s
			raise ValueError(f"Symbol {symbol} not found")
		return self._get_symbol_info_cached(symbol, _fetch)

	# Read helpers
	def get_mark_price(self, symbol: str) -> Optional[float]:
		try:
			mp = self.client.mark_price(symbol=symbol)
			return float(mp.get("markPrice")) if isinstance(mp, dict) else None
		except Exception:
			return None

	def get_open_orders(self, symbol: str) -> list:
		try:
			return self.client.get_open_orders(symbol=symbol)
		except Exception:
			return []

	def get_all_open_orders(self) -> List[dict]:
		try:
			return self.client.get_open_orders()
		except Exception:
			return []

	def get_nonzero_position_symbols(self) -> Set[str]:
		try:
			acc = self.client.account(recvWindow=self.recv_window_ms)
			s = set()
			for p in acc.get("positions", []):
				try:
					if abs(float(p.get("positionAmt", 0) or 0)) > 0:
						s.add(p.get("symbol"))
				except Exception:
					pass
			return s
		except Exception:
			return set()

	def get_position(self, symbol: str) -> Optional[dict]:
		try:
			acc = self.client.account(recvWindow=self.recv_window_ms)
			for p in acc.get("positions", []):
				if p.get("symbol") == symbol:
					return p
			return None
		except Exception:
			return None

	def cancel_order(self, symbol: str, *, order_id: Optional[Any] = None, client_order_id: Optional[str] = None) -> bool:  # type: ignore
		try:
			if order_id is not None:
				self.client.cancel_order(symbol=symbol, orderId=int(order_id))
				return True
			if client_order_id:
				self.client.cancel_order(symbol=symbol, origClientOrderId=client_order_id)
				return True
			return False
		except Exception:
			return False

	def cancel_all_open_orders(self, symbol: str) -> bool:
		try:
			self.client.cancel_open_orders(symbol=symbol)
			return True
		except Exception:
			return False

	def get_usdt_balance(self, balance_type: str = "available") -> float:
		acc = self.client.account(recvWindow=self.recv_window_ms)
		for a in acc.get("assets", []):
			if a.get("asset") == "USDT":
				if balance_type == "available":
					return float(a.get("availableBalance", 0) or 0)
				return float(a.get("walletBalance", a.get("marginBalance", 0)) or 0)
		raise RuntimeError("USDT not found in assets")

	# account setup
	def set_margin_type(self, symbol: str, margin_type: str) -> None:
		try:
			self.client.change_margin_type(symbol=symbol, marginType=margin_type, recvWindow=self.recv_window_ms)
		except Exception:
			pass

	def set_leverage(self, symbol: str, leverage: int) -> None:
		try:
			self.client.change_leverage(symbol=symbol, leverage=leverage, recvWindow=self.recv_window_ms)
		except Exception:
			pass

	# placement
	def place_limit_entry(self, symbol: str, side: str, price: str, qty: str, tif: str, position_side: str) -> dict:
		return self.client.new_order(symbol=symbol, side=side, type="LIMIT", timeInForce=tif, price=price, quantity=qty, positionSide=position_side, recvWindow=self.recv_window_ms)

	def place_stop_loss(self, symbol: str, side: str, stop_price: str, qty: str, position_side: str, reduce_only: bool, working_type: str, mode: str = 'market') -> dict:
		return self.client.new_order(symbol=symbol, side=side, type="STOP_MARKET", stopPrice=stop_price, quantity=qty, reduceOnly=reduce_only, positionSide=position_side, workingType=working_type, recvWindow=self.recv_window_ms)

	def place_take_profit(self, symbol: str, side: str, stop_price: str, qty: str, position_side: str, reduce_only: bool, working_type: str, mode: str = 'market') -> dict:
		return self.client.new_order(symbol=symbol, side=side, type="TAKE_PROFIT_MARKET", stopPrice=stop_price, quantity=qty, reduceOnly=reduce_only, positionSide=position_side, workingType=working_type, recvWindow=self.recv_window_ms)

	def place_trailing(self, symbol: str, side: str, activation_price: str, callback_rate: str, qty: str, position_side: str, reduce_only: bool, working_type: str, mode: str = 'market') -> dict:
		payload = {
			"symbol": symbol,
			"side": side,
			"type": "TRAILING_STOP_MARKET",
			"activationPrice": activation_price,
			"callbackRate": callback_rate,
			"quantity": qty,
			"reduceOnly": reduce_only,
			"positionSide": position_side,
			"recvWindow": self.recv_window_ms,
		}
		return self.client.new_order(**payload)


class PortfolioPMConnector(BaseFuturesConnector):
	"""Portfolio Margin (PAPI) connector.
	Core rule: for signed endpoints, signature payload must match exactly the request body string when we send `application/x-www-form-urlencoded`.
	"""

	def __init__(self, *, api_key: str, api_secret: str, testnet: bool = False, recv_window_ms: int = 60000, log: bool = True, use_conditional: bool = True, strategy_type: str = "1") -> None:
		super().__init__(api_key=api_key, api_secret=api_secret, testnet=testnet, recv_window_ms=recv_window_ms, log=log)
		self.base_url = "https://papi.binance.com"
		self._use_conditional = bool(use_conditional)
		self._strategy_type = str(strategy_type)
		# we will reuse UMFutures exchange_info to get filters
		if UMFutures is None:
			raise RuntimeError("python-binance UMFutures not available for exchange_info")
		# Ensure UMFutures has a valid base_url (some versions don't set attribute if None)
		um_base_url = ("https://testnet.binancefuture.com" if testnet else "https://fapi.binance.com")
		self._um = UMFutures(key=api_key, secret=api_secret, base_url=um_base_url)
		# short-lived cache for account snapshot (positions/balances)
		self._last_account: Optional[dict] = None
		self._last_account_ts: float = 0.0
		self._account_cache_ttl_sec: float = 2.0

	def _headers(self) -> Dict[str, str]:
		return {"X-MBX-APIKEY": self.api_key, "X-MBX-PORTFOLIO-MARGIN": "true"}

	def _sign(self, payload: str) -> str:
		return hmac.new(self.api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

	def _pm_request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, *, send_in_body: bool = False) -> Any:
		if params is None:
			params = {}
		params.setdefault("recvWindow", self.recv_window_ms)
		params.setdefault("timestamp", int(time.time() * 1000))
		# normalize types
		string_keys = {"orderType", "side", "positionSide", "workingType", "timeInForce", "priceProtect", "reduceOnly"}
		for k, v in list(params.items()):
			if k in string_keys and v is not None:
				params[k] = str(v)
		if "strategyType" in params and params["strategyType"] is not None:
			# keep as string per PAPI examples
			params["strategyType"] = str(params["strategyType"]) or "1"
		# payload for signing
		sorted_items = sorted([(k, params[k]) for k in params.keys() if params[k] is not None])
		payload_str = urlencode(sorted_items, doseq=True, quote_via=quote)
		signature = self._sign(payload_str)
		headers = {**self._headers()}
		if method.upper() == "GET":
			full_url = f"{self.base_url}{path}?{payload_str}&signature={signature}"
			r = self._http.request(method, full_url, headers=headers)
			self._log_req("PM GET", path, params)
		else:
			# For POST/DELETE: if send_in_body True, put params into body and only signature in query
			if send_in_body:
				full_url = f"{self.base_url}{path}?signature={signature}"
				headers["Content-Type"] = "application/x-www-form-urlencoded"
				r = self._http.request(method, full_url, data=payload_str, headers=headers)
				self._log_req("PM BODY", path, params)
			else:
				full_url = f"{self.base_url}{path}?{payload_str}&signature={signature}"
				r = self._http.request(method, full_url, headers=headers)
				self._log_req("PM QRY", path, params)
		try:
			r.raise_for_status()
		except Exception:
			self._log("pm_request_failed", {"method": method, "path": path, "status": r.status_code, "body": r.text})
			raise
		try:
			resp = r.json()
			self._log_resp("PM RESP", r.status_code, resp)
			return resp
		except Exception:
			return {}
		try:
			r.raise_for_status()
		except Exception:
			self._log("pm_request_failed", {"method": method, "path": path, "status": r.status_code, "body": r.text})
			raise
		try:
			return r.json()
		except Exception:
			return {}

	# Metadata (via UMFutures)
	def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
		def _fetch():
			info = self._um.exchange_info()
			for s in info.get("symbols", []):
				if s.get("symbol") == symbol:
					return s
			raise ValueError(f"Symbol {symbol} not found")
		return self._get_symbol_info_cached(symbol, _fetch)

	def get_mark_price(self, symbol: str) -> Optional[float]:
		try:
			mp = self._um.mark_price(symbol=symbol)
			return float(mp.get("markPrice")) if isinstance(mp, dict) else None
		except Exception:
			return None

	def _get_account_cached(self) -> dict:
		now = time.time()
		if self._last_account and (now - self._last_account_ts) < self._account_cache_ttl_sec:
			return self._last_account
		acc = self._pm_request("GET", "/papi/v1/um/account", {})
		self._last_account = acc if isinstance(acc, dict) else {}
		self._last_account_ts = now
		return self._last_account

	def get_all_open_orders(self) -> List[dict]:
		orders: List[dict] = []
		# standard
		try:
			resp = self._pm_request("GET", "/papi/v1/um/openOrders", {})
			if isinstance(resp, list):
				orders.extend(resp)
		except Exception:
			pass
		# conditional
		try:
			cres = self._pm_request("GET", "/papi/v1/um/conditional/openOrders", {})
			if isinstance(cres, list):
				for o in cres:
					if "type" not in o and "strategyType" in o:
						o["type"] = o.get("orderType") or o.get("strategyType")
					orders.append(o)
		except Exception:
			pass
		return orders

	def get_open_orders(self, symbol: str) -> list:
		orders: list = []
		try:
			resp = self._pm_request("GET", "/papi/v1/um/openOrders", {"symbol": symbol})
			if isinstance(resp, list):
				orders.extend(resp)
		except Exception:
			pass
		# Only use one valid conditional endpoint to avoid 404s
		try:
			cres = self._pm_request("GET", "/papi/v1/um/conditional/openOrders", {"symbol": symbol})
			if isinstance(cres, list):
				for o in cres:
					if "type" not in o and "strategyType" in o:
						o["type"] = o.get("orderType") or o.get("strategyType")
					orders.append(o)
		except Exception:
			pass
		return orders

	def get_nonzero_position_symbols(self) -> Set[str]:
		try:
			acc = self._get_account_cached()
			s = set()
			for p in acc.get("positions", []):
				try:
					if abs(float(p.get("positionAmt", 0) or 0)) > 0:
						s.add(p.get("symbol"))
				except Exception:
					pass
			return s
		except Exception:
			return set()

	def get_position(self, symbol: str) -> Optional[dict]:
		try:
			acc = self._get_account_cached()
			for p in acc.get("positions", []):
				if p.get("symbol") == symbol:
					return p
			return None
		except Exception:
			return None

	def cancel_order(self, symbol: str, *, order_id: Optional[Any] = None, client_order_id: Optional[str] = None) -> bool:  # type: ignore
		params: Dict[str, Any] = {"symbol": symbol}
		if order_id is not None:
			params["orderId"] = int(order_id)
		elif client_order_id:
			params["origClientOrderId"] = client_order_id
		else:
			return False
		try:
			self._pm_request("DELETE", "/papi/v1/um/order", params)
			return True
		except Exception:
			return False

	def cancel_all_open_orders(self, symbol: str) -> bool:
		ok = True
		try:
			self._pm_request("DELETE", "/papi/v1/um/allOpenOrders", {"symbol": symbol})
		except Exception:
			ok = False
		# Also cancel all open conditional orders
		try:
			self._pm_request("DELETE", "/papi/v1/um/conditional/allOpenOrders", {"symbol": symbol})
		except Exception:
			pass
		return ok

	def get_usdt_balance(self, balance_type: str = "available") -> float:
		# Use PM consolidated balance only: GET /papi/v1/balance → USDT row
		try:
			pm_balance_list = []
			try:
				pm_balance_list = self._pm_request("GET", "/papi/v1/balance", {}) or []
			except Exception:
				pm_balance_list = []
			pm_usdt = None
			for it in (pm_balance_list or []):
				try:
					if it.get("asset") == "USDT":
						pm_usdt = it
						break
				except Exception:
					pass
			if not pm_usdt:
				self._log("[BAL] no USDT row in /papi/v1/balance", json.dumps(pm_balance_list[:1] if isinstance(pm_balance_list, list) else {}, ensure_ascii=False))
				return 0.0
			# Extract primary fields
			def _to_f(v):
				try:
					return float(v)
				except Exception:
					return None
			avail = _to_f(pm_usdt.get("availableBalance"))
			withdraw_avail = _to_f(pm_usdt.get("withdrawAvailable"))
			total_wallet = _to_f(pm_usdt.get("totalWalletBalance"))
			um_w = _to_f(pm_usdt.get("umWalletBalance"))
			um_upnl = _to_f(pm_usdt.get("umUnrealizedPNL"))
			cm_w = _to_f(pm_usdt.get("cmWalletBalance"))
			cm_upnl = _to_f(pm_usdt.get("cmUnrealizedPNL"))
			# Decide by requested type
			chosen = 0.0
			source = "none"
			if str(balance_type).lower() == "available":
				# Prefer availableBalance; fallback to withdrawAvailable
				if avail is not None and avail > 0:
					chosen = avail
					source = "availableBalance"
				elif withdraw_avail is not None:
					chosen = withdraw_avail
					source = "withdrawAvailable"
			else:
				# Prefer totalWalletBalance as consolidated collateral, else sum of UM/CM wallet + PnL
				if total_wallet is not None and total_wallet >= 0:
					chosen = total_wallet
					source = "totalWalletBalance"
				else:
					um_equity = (um_w or 0.0) + (um_upnl or 0.0)
					cm_equity = (cm_w or 0.0) + (cm_upnl or 0.0)
					chosen = um_equity + cm_equity
					source = "um+cm equity"
			self._log("[BAL] chosen", json.dumps({
				"type": balance_type,
				"asset": "USDT",
				"availableBalance": avail,
				"withdrawAvailable": withdraw_avail,
				"totalWalletBalance": total_wallet,
				"umWalletBalance": um_w,
				"umUnrealizedPNL": um_upnl,
				"cmWalletBalance": cm_w,
				"cmUnrealizedPNL": cm_upnl,
				"chosen": chosen,
				"source": source
			}, ensure_ascii=False))
			return float(chosen or 0.0)
		except Exception:
			raise RuntimeError("Failed to fetch account balance from /papi/v1/balance")

	# placement
	def place_limit_entry(self, symbol: str, side: str, price: str, qty: str, tif: str, position_side: str) -> dict:
		return self._pm_request("POST", "/papi/v1/um/order", {
			"symbol": symbol,
			"side": side,
			"type": "LIMIT",
			"timeInForce": tif,
			"quantity": qty,
			"price": price,
			"positionSide": position_side,
		})

	def _maybe_use_conditional(self) -> bool:
		return self._use_conditional

	def place_stop_loss(self, symbol: str, side: str, stop_price: str, qty: str, position_side: str, reduce_only: bool, working_type: str, mode: str = 'auto') -> dict:
		if mode == 'auto':
			use_cond = self._maybe_use_conditional()
		else:
			use_cond = (mode == 'conditional')
		if use_cond:
			# PAPI conditional STOP requires orderType=STOP with price+stopPrice and timeInForce
			return self._pm_request("POST", "/papi/v1/um/conditional/order", {
				"symbol": symbol,
				"side": side,
				"orderType": "STOP",
				"strategyType": "STOP",
				"price": stop_price,
				"stopPrice": stop_price,
				"timeInForce": "GTC",
				"quantity": qty,
				"reduceOnly": str(bool(reduce_only)).lower(),
				"positionSide": position_side,
				"workingType": working_type,
				"priceProtect": "false",
			}, send_in_body=True)
		# fallback to order endpoint (STOP_MARKET)
		return self._pm_request("POST", "/papi/v1/um/order", {
			"symbol": symbol,
			"side": side,
			"type": "STOP_MARKET",
			"stopPrice": stop_price,
			"quantity": qty,
			"reduceOnly": str(bool(reduce_only)).lower(),
			"positionSide": position_side,
			"workingType": working_type,
			"priceProtect": "false",
		})

	def place_take_profit(self, symbol: str, side: str, stop_price: str, qty: str, position_side: str, reduce_only: bool, working_type: str, mode: str = 'auto') -> dict:
		if mode == 'auto':
			use_cond = self._maybe_use_conditional()
		else:
			use_cond = (mode == 'conditional')
		if use_cond:
			# PAPI conditional TAKE_PROFIT requires orderType=TAKE_PROFIT with price+stopPrice and timeInForce
			return self._pm_request("POST", "/papi/v1/um/conditional/order", {
				"symbol": symbol,
				"side": side,
				"orderType": "TAKE_PROFIT",
				"strategyType": "TAKE_PROFIT",
				"price": stop_price,
				"stopPrice": stop_price,
				"timeInForce": "GTC",
				"quantity": qty,
				"reduceOnly": str(bool(reduce_only)).lower(),
				"positionSide": position_side,
				"workingType": working_type,
				"priceProtect": "false",
			}, send_in_body=True)
		return self._pm_request("POST", "/papi/v1/um/order", {
			"symbol": symbol,
			"side": side,
			"type": "TAKE_PROFIT_MARKET",
			"stopPrice": stop_price,
			"quantity": qty,
			"reduceOnly": str(bool(reduce_only)).lower(),
			"positionSide": position_side,
			"workingType": working_type,
			"priceProtect": "false",
		})

	def place_trailing(self, symbol: str, side: str, activation_price: str, callback_rate: str, qty: str, position_side: str, reduce_only: bool, working_type: str, mode: str = 'auto') -> dict:
		if mode == 'auto':
			use_cond = self._maybe_use_conditional()
		else:
			use_cond = (mode == 'conditional')
		if use_cond:
			return self._pm_request("POST", "/papi/v1/um/conditional/order", {
				"symbol": symbol,
				"side": side,
				"orderType": "TRAILING_STOP_MARKET",
				"strategyType": "TRAILING_STOP_MARKET",
				"activationPrice": activation_price,
				"callbackRate": callback_rate,
				"quantity": qty,
				"reduceOnly": str(bool(reduce_only)).lower(),
				"positionSide": position_side,
				"workingType": working_type,
				"priceProtect": "false",
			}, send_in_body=True)
		return self._pm_request("POST", "/papi/v1/um/order", {
			"symbol": symbol,
			"side": side,
			"type": "TRAILING_STOP_MARKET",
			"activationPrice": activation_price,
			"callbackRate": callback_rate,
			"quantity": qty,
			"reduceOnly": str(bool(reduce_only)).lower(),
			"positionSide": position_side,
			"workingType": working_type,
			"priceProtect": "false",
		}) 