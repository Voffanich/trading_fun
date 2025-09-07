from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple

from binance.um_futures import UMFutures
from binance.error import ClientError
import json
from datetime import datetime
import os
from decimal import Decimal, ROUND_DOWN, getcontext


@dataclass
class OrderResult:
	success: bool
	message: str
	error_code: Optional[int] = None
	entry_order: Optional[Dict[str, Any]] = None
	stop_order: Optional[Dict[str, Any]] = None
	take_profit_order: Optional[Dict[str, Any]] = None
	trailing_stop_order: Optional[Dict[str, Any]] = None
	raw: Dict[str, Any] = field(default_factory=dict)


class Binance_connect:
	"""
	USDT-M Futures connector for placing orders on a Binance subaccount.

	Required inputs for placing a trade:
	- symbol: trading pair, e.g. "ETHUSDT"
	- side: "BUY" for long entry, "SELL" for short entry
	- entry_price: target entry price from bot logic
	- deviation_percent: percent offset from entry price to place a limit order. For BUY it places lower, for SELL it places higher
	- stop_loss_price: protective stop price
	- trailing_activation_price: price at which the trailing stop becomes active
	- trailing_callback_percent: trailing callback rate (0.1% - 5% per Binance)
	- leverage: leverage to set before placing orders

	Optional:
	- quantity: explicit contract quantity; if omitted, you must provide either notional_usdt or risk inputs via your own logic before calling
	- notional_usdt: desired notional in USDT used to derive quantity from entry price
	- take_profit_price: optional take-profit price
	- margin_type: "ISOLATED" (default) or "CROSSED"
	- reduce_only: ensure protective orders cannot increase exposure (default True)
	- working_type: trigger reference for stop orders ("MARK_PRICE" default or "CONTRACT_PRICE")
	- time_in_force: TIF for limit orders (default GTC)
	- position_side: for hedge mode ("BOTH" default when one-way mode)
	- testnet: constructor flag to use Binance Futures testnet
	- skip_account_setup: if True, do NOT change margin type or leverage inside the method (default False)
	- log_to_file: if True, write structured JSON logs to a file (default False)
	- log_file_path: path to the log file (default "logs/binance_connector.log")
	"""

	def __init__(self, api_key: str, api_secret: str, testnet: bool = False, recv_window_ms: int = 60000, *, log_to_file: bool = False, log_file_path: Optional[str] = None) -> None:
		if testnet:
			self.client = UMFutures(key=api_key, secret=api_secret, base_url="https://testnet.binancefuture.com")
		else:
			self.client = UMFutures(key=api_key, secret=api_secret)
		self.recv_window_ms = recv_window_ms
		self.log_to_file = log_to_file
		self.log_file_path = log_file_path or os.path.join("logs", "binance_connector.log")
		if self.log_to_file:
			os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)

	# -------- Logging --------
	def _write_file_log(self, event: str, details: Optional[Dict[str, Any]] = None) -> None:
		if not self.log_to_file:
			return
		record = {
			"ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
			"event": event,
			"details": details or {},
		}
		try:
			with open(self.log_file_path, "a", encoding="utf-8") as f:
				f.write(json.dumps(record, ensure_ascii=False) + "\n")
		except Exception:
			pass

	def _log(self, verbose: bool, message: str, details: Optional[Dict[str, Any]] = None) -> None:
		# Console
		if verbose:
			ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
			print(f"[{ts}] [Binance_connect] {message}")
			if details:
				try:
					print("  " + json.dumps(details, ensure_ascii=False, separators=(",", ":")))
				except Exception:
					print("  " + str(details))
		# File
		self._write_file_log(message, details)

	# -------- Symbol metadata and rounding --------
	def _get_symbol_info(self, symbol: str) -> Dict[str, Any]:
		info = self.client.exchange_info()
		for item in info.get("symbols", []):
			if item.get("symbol") == symbol:
				return item
		raise ValueError(f"Symbol {symbol} not found in exchange info")

	def _get_filters(self, symbol_info: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
		filters: Dict[str, Dict[str, Any]] = {}
		for f in symbol_info.get("filters", []):
			filters[f.get("filterType")] = f
		return filters

	# -------- Decimal helpers strictly matching Binance filters --------
	def _quantum_from_step(self, step_str: str) -> Decimal:
		"""Return Decimal quantum for quantize based on a Binance step string (e.g. '0.0001' or '1e-8')."""
		if not step_str:
			step_str = "1"
		return Decimal(step_str)

	def _format_by_step(self, value: float, step_str: str) -> str:
		"""Quantize value DOWN to the given step and return as plain string without excess trailing zeros."""
		getcontext().prec = 28
		quant = self._quantum_from_step(step_str)
		q = (Decimal(str(value))).quantize(quant, rounding=ROUND_DOWN)
		s = format(q, 'f')
		if '.' in s:
			s = s.rstrip('0').rstrip('.') or '0'
		return s

	def _tick_size(self, filters: Dict[str, Dict[str, Any]]) -> float:
		pf = filters.get("PRICE_FILTER", {})
		return float(pf.get("tickSize", 0.0)) or 0.0

	def _step_size(self, filters: Dict[str, Dict[str, Any]]) -> float:
		ls = filters.get("LOT_SIZE", {})
		return float(ls.get("stepSize", 0.0)) or 0.0

	def _min_qty(self, filters: Dict[str, Dict[str, Any]]) -> float:
		ls = filters.get("LOT_SIZE", {})
		return float(ls.get("minQty", 0.0)) or 0.0

	def _min_notional(self, filters: Dict[str, Dict[str, Any]]) -> float:
		mn = filters.get("MIN_NOTIONAL", {})
		return float(mn.get("notional", mn.get("minNotional", 0.0)) or 0.0)

	def _round_to_step(self, value: float, step: float) -> float:
		if step == 0:
			return value
		n_steps = int(value / step)
		return n_steps * step

	def _round_price(self, price: float, tick_size: float) -> float:
		return self._round_to_step(price, tick_size)

	def _round_qty(self, qty: float, step_size: float, min_qty: float) -> float:
		rounded = self._round_to_step(qty, step_size)
		if rounded < min_qty:
			return 0.0
		return rounded

	# -------- Public helpers for orders and positions --------
	def get_open_orders(self, symbol: str) -> list:
		try:
			return self.client.get_open_orders(symbol=symbol)
		except ClientError as e:
			self._log(True, "get_open_orders failed", {"symbol": symbol, "error": getattr(e, "error_message", str(e))})
			return []

	def get_all_open_orders(self) -> list:
		"""Return all open orders across symbols (UMFutures supports no-symbol call)."""
		try:
			return self.client.get_open_orders()
		except TypeError as e:
			# Some client versions require a symbol. We'll log and return empty to allow caller fallback.
			self._log(True, "get_all_open_orders unsupported without symbol", {"error": str(e)})
			return []
		except ClientError as e:
			self._log(True, "get_all_open_orders failed", {"error": getattr(e, "error_message", str(e))})
			return []

	def get_order(self, symbol: str, *, order_id: Optional[int] = None, client_order_id: Optional[str] = None) -> Optional[dict]:
		try:
			if order_id is not None:
				return self.client.get_order(symbol=symbol, orderId=order_id)
			elif client_order_id is not None:
				return self.client.get_order(symbol=symbol, origClientOrderId=client_order_id)
			return None
		except ClientError as e:
			self._log(True, "get_order failed", {"symbol": symbol, "error": getattr(e, "error_message", str(e))})
			return None

	def cancel_order(self, symbol: str, *, order_id: Optional[Any] = None, client_order_id: Optional[str] = None) -> bool:
		"""Cancel by numeric orderId or string clientOrderId; safely ignore empty/invalid IDs."""
		def _is_valid_order_id(oid: Optional[Any]) -> bool:
			if oid is None:
				return False
			# allow numeric > 0 or non-empty digit string
			if isinstance(oid, int):
				return oid > 0
			if isinstance(oid, str):
				return oid.strip().isdigit()
			return False
		try:
			if _is_valid_order_id(order_id):
				self._log(True, "cancel_order attempt", {"symbol": symbol, "order_id": order_id})
				self.client.cancel_order(symbol=symbol, orderId=int(order_id))
				return True
			elif client_order_id is not None and isinstance(client_order_id, str) and client_order_id.strip():
				self._log(True, "cancel_order attempt by clientOrderId", {"symbol": symbol, "client_order_id": client_order_id})
				self.client.cancel_order(symbol=symbol, origClientOrderId=client_order_id)
				return True
			else:
				self._log(True, "cancel_order skipped", {"symbol": symbol, "order_id": order_id, "client_order_id": client_order_id, "reason": "empty or invalid ID"})
				return False
		except ClientError as e:
			self._log(True, "cancel_order failed", {"symbol": symbol, "order_id": order_id, "client_order_id": client_order_id, "error": getattr(e, "error_message", str(e))})
			return False
		except Exception as e:
			# Catch TypeError like: orderId is mandatory, but received empty
			self._log(True, "cancel_order failed (unexpected)", {"symbol": symbol, "order_id": order_id, "client_order_id": client_order_id, "error": str(e)})
			return False

	def cancel_all_open_orders(self, symbol: str) -> bool:
		try:
			self.client.cancel_open_orders(symbol=symbol)
			return True
		except ClientError as e:
			self._log(True, "cancel_all_open_orders failed", {"symbol": symbol, "error": getattr(e, "error_message", str(e))})
			return False

	def get_mark_price(self, symbol: str) -> Optional[float]:
		try:
			mp = self.client.mark_price(symbol=symbol)
			return float(mp.get("markPrice")) if isinstance(mp, dict) and mp.get("markPrice") is not None else None
		except ClientError as e:
			self._log(True, "get_mark_price failed", {"symbol": symbol, "error": getattr(e, "error_message", str(e))})
			return None

	def get_position(self, symbol: str) -> Optional[dict]:
		try:
			positions = self.client.account(recvWindow=self.recv_window_ms)
			for p in positions.get("positions", []):
				if p.get("symbol") == symbol:
					return p
			return None
		except ClientError as e:
			self._log(True, "get_position failed", {"symbol": symbol, "error": getattr(e, "error_message", str(e))})
			return None

	def get_nonzero_position_symbols(self) -> list:
		"""Return list of symbols with non-zero absolute positionAmt."""
		try:
			acc = self.client.account(recvWindow=self.recv_window_ms)
			symbols = []
			for p in acc.get("positions", []):
				try:
					amt = float(p.get("positionAmt", 0) or 0)
					if abs(amt) > 0:
						symbols.append(p.get("symbol"))
				except Exception:
					continue
			return symbols
		except ClientError as e:
			self._log(True, "get_nonzero_position_symbols failed", {"error": getattr(e, "error_message", str(e))})
			return []

	def get_all_positions(self) -> list:
		"""Return raw positions array from account()."""
		try:
			acc = self.client.account(recvWindow=self.recv_window_ms)
			return acc.get("positions", []) or []
		except ClientError as e:
			self._log(True, "get_all_positions failed", {"error": getattr(e, "error_message", str(e))})
			return []

	# -------- Risk helpers --------
	def derive_quantity(self, *, notional_usdt: Optional[float], entry_price: float, step_size: float, min_qty: float) -> float:
		if notional_usdt is None:
			raise ValueError("Either quantity or notional_usdt must be provided to compute quantity")
		qty = notional_usdt / entry_price
		qty = self._round_qty(qty, step_size, min_qty)
		if qty <= 0:
			raise ValueError("Calculated quantity is below the minimum lot size")
		return qty

	def derive_quantity_by_risk(
		self,
		*,
		bank_usdt: float,
		risk_percent: float,
		entry_price: float,
		stop_loss_price: float,
		step_size: float,
		min_qty: float,
	) -> float:
		"""
		Risk-based position sizing for USDT-M linear contracts.
		Risk amount = bank_usdt * (risk_percent / 100).
		Per-unit loss at stop = abs(entry_price - stop_loss_price).
		Quantity = Risk amount / Per-unit loss.
		Note: Leverage affects margin requirement, not PnL at stop.
		"""
		if bank_usdt <= 0:
			raise ValueError("bank_usdt must be positive")
		if risk_percent <= 0:
			raise ValueError("risk_percent must be positive")
		delta = abs(entry_price - stop_loss_price)
		if delta <= 0:
			raise ValueError("entry_price and stop_loss_price must differ for risk calculation")
		risk_amount = bank_usdt * (risk_percent / 100.0)
		qty_raw = risk_amount / delta
		qty = self._round_qty(qty_raw, step_size, min_qty)
		if qty <= 0:
			raise ValueError("Calculated quantity is below the minimum lot size")
		return qty

	def get_usdt_balance(self, balance_type: str = "wallet") -> float:
		"""
		Fetch USDT balance from USDT-M Futures account.
		balance_type: "wallet" (default) or "available"
		"""
		try:
			data = self.client.account(recvWindow=self.recv_window_ms)
			self._write_file_log("account", {"response": data})
			for asset in data.get("assets", []):
				if asset.get("asset") == "USDT":
					if balance_type == "available":
						return float(asset.get("availableBalance"))
					return float(asset.get("walletBalance"))
			raise RuntimeError("USDT asset not found in account assets")
		except ClientError as e:
			self._write_file_log("account_error", {"error": getattr(e, "error_message", str(e))})
			raise RuntimeError(f"Failed to fetch account balance: {e}")

	def compute_quantity_from_risk(
		self,
		symbol: str,
		entry_price: float,
		stop_loss_price: float,
		risk_percent_of_bank: float,
		*,
		balance_type: str = "available",
		verbose: bool = False,
	) -> float:
		"""
		Convenience wrapper: reads filters and current USDT balance (available by default), then derives quantity by risk and rounds to lot size.
		"""
		self._log(verbose, "Fetching symbol filters for sizing", {"symbol": symbol})
		symbol_info = self._get_symbol_info(symbol)
		filters = self._get_filters(symbol_info)
		step_size = self._step_size(filters)
		min_qty = self._min_qty(filters)
		self._log(verbose, "Fetching USDT balance", {"balance_type": balance_type})
		bank = self.get_usdt_balance(balance_type=balance_type)
		self._log(verbose, "Balance fetched", {"bank_usdt": bank})
		# Detailed sizing math
		delta = abs(entry_price - stop_loss_price)
		risk_amount = bank * (risk_percent_of_bank / 100.0)
		qty_raw = risk_amount / delta if delta > 0 else 0
		qty_rounded = self._round_qty(qty_raw, step_size, min_qty)
		self._log(verbose, "Sizing by risk", {
			"entry_price": entry_price,
			"stop_loss_price": stop_loss_price,
			"delta": delta,
			"bank_usdt": bank,
			"risk_percent": risk_percent_of_bank,
			"risk_amount": risk_amount,
			"step_size": step_size,
			"min_qty": min_qty,
			"qty_raw": qty_raw,
			"qty_rounded": qty_rounded,
		})
		return qty_rounded

	# -------- Account setup --------
	def set_leverage(self, symbol: str, leverage: int) -> None:
		try:
			resp = self.client.change_leverage(symbol=symbol, leverage=leverage, recvWindow=self.recv_window_ms)
			self._write_file_log("change_leverage", {"symbol": symbol, "leverage": leverage, "response": resp})
		except ClientError as e:
			code = getattr(e, "error_code", None) or getattr(e, "status_code", None)
			self._write_file_log("change_leverage_error", {"symbol": symbol, "leverage": leverage, "error": getattr(e, "error_message", str(e)), "code": code})
			if code in (-2015, 401):
				raise RuntimeError("Failed to set leverage: invalid API key, IP whitelist, or missing Futures permissions")
			raise RuntimeError(f"Failed to set leverage: {e}")

	def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED") -> None:
		try:
			resp = self.client.change_margin_type(symbol=symbol, marginType=margin_type, recvWindow=self.recv_window_ms)
			self._write_file_log("change_margin_type", {"symbol": symbol, "margin_type": margin_type, "response": resp})
		except ClientError as e:
			# If already set, Binance returns error code; ignore that specific case
			msg = getattr(e, "error_message", "")
			code = getattr(e, "error_code", None) or getattr(e, "status_code", None)
			self._write_file_log("change_margin_type_error", {"symbol": symbol, "margin_type": margin_type, "error": msg, "code": code})
			if "No need to change margin type" in str(msg):
				return
			if code in (-2015, 401):
				raise RuntimeError("Failed to set margin type: invalid API key, IP whitelist, or missing Futures permissions")
			raise RuntimeError(f"Failed to set margin type: {e}")

	# -------- Validation --------
	def _validate_qty_notional(self, *, price: float, qty: float, min_qty: float, min_notional: float) -> None:
		if qty < min_qty:
			raise ValueError(f"Quantity {qty} is below minQty {min_qty}")
		notional = price * qty
		if min_notional > 0 and notional < min_notional:
			raise ValueError(f"Order notional {notional} is below minNotional {min_notional}")

	def _clamp_callback_rate(self, callback_percent: float) -> float:
		# Binance USDT-M allows 0.1% - 5% and requires 0.1% step
		try:
			val = float(callback_percent)
		except Exception:
			val = 0.1
		# round to one decimal (0.1 step)
		val = round(val, 1)
		# enforce bounds
		if val < 0.1:
			val = 0.1
		elif val > 5.0:
			val = 5.0
		return val

	# -------- Main placement --------
	def place_futures_order_with_protection(
		self,
		symbol: str,
		side: str,
		entry_price: float,
		deviation_percent: float,
		stop_loss_price: float,
		trailing_activation_price: float,
		trailing_callback_percent: float,
		leverage: int,
		*,
		quantity: Optional[float] = None,
		notional_usdt: Optional[float] = None,
		risk_percent_of_bank: Optional[float] = None,
		current_bank_usdt: Optional[float] = None,
		take_profit_price: Optional[float] = None,
		margin_type: str = "ISOLATED",
		reduce_only: bool = True,
		working_type: str = "MARK_PRICE",
		time_in_force: str = "GTC",
		position_side: str = "BOTH",
		skip_account_setup: bool = False,
		verbose: bool = False,
		trailing_size_mode: str = "quantity",  # "quantity" (reduceOnly qty) | "close_position"
		risk_balance_type: str = "available",
	) -> OrderResult:
		"""
		Places an entry LIMIT order offset by deviation_percent from entry_price and adds stop-loss,
		optional take-profit, and trailing-stop reduce-only orders.
		"""
		orders_raw: Dict[str, Any] = {}
		try:
			# 0) Input summary
			input_summary = {
				"symbol": symbol,
				"side": side,
				"entry_price": entry_price,
				"deviation_percent": deviation_percent,
				"stop_loss_price": stop_loss_price,
				"trailing_activation_price": trailing_activation_price,
				"trailing_callback_percent": trailing_callback_percent,
				"leverage": leverage,
				"quantity": quantity,
				"notional_usdt": notional_usdt,
				"risk_percent_of_bank": risk_percent_of_bank,
				"current_bank_usdt": current_bank_usdt,
				"margin_type": margin_type,
				"position_side": position_side,
				"working_type": working_type,
				"time_in_force": time_in_force,
				"trailing_size_mode": trailing_size_mode,
			}
			self._log(verbose, "Received placement request", input_summary)

			# 1) Symbol metadata and rounding
			symbol_info = self._get_symbol_info(symbol)
			filters = self._get_filters(symbol_info)
			pf = filters.get("PRICE_FILTER", {})
			ls = filters.get("LOT_SIZE", {})
			tick_size = self._tick_size(filters)
			step_size = self._step_size(filters)
			min_qty = self._min_qty(filters)
			min_notional = self._min_notional(filters)
			filters_summary = {
				"tick_size": tick_size,
				"step_size": step_size,
				"min_qty": min_qty,
				"min_notional": min_notional,
			}
			self._log(verbose, "Symbol filters loaded", filters_summary)

			# 2) Account setup (optional)
			if not skip_account_setup:
				self.set_margin_type(symbol, margin_type)
				self.set_leverage(symbol, leverage)
				self._log(verbose, "Account configured", {"margin_type": margin_type, "leverage": leverage})

			# 3) Determine quantity if not provided
			if quantity is None:
				if notional_usdt is not None:
					quantity = self.derive_quantity(
						notional_usdt=notional_usdt,
						entry_price=entry_price,
						step_size=step_size,
						min_qty=min_qty,
					)
					self._log(verbose, "Quantity derived from notional", {"notional_usdt": notional_usdt, "quantity_raw": quantity})
				elif risk_percent_of_bank is not None and current_bank_usdt is not None:
					quantity = self.derive_quantity_by_risk(
						bank_usdt=current_bank_usdt,
						risk_percent=risk_percent_of_bank,
						entry_price=entry_price,
						stop_loss_price=stop_loss_price,
						step_size=step_size,
						min_qty=min_qty,
					)
					self._log(verbose, "Quantity derived from explicit bank+risk", {"bank_usdt": current_bank_usdt, "risk_percent": risk_percent_of_bank, "quantity_raw": quantity})
				elif risk_percent_of_bank is not None and current_bank_usdt is None:
					quantity = self.compute_quantity_from_risk(
						symbol=symbol,
						entry_price=entry_price,
						stop_loss_price=stop_loss_price,
						risk_percent_of_bank=risk_percent_of_bank,
						balance_type=risk_balance_type,
						verbose=verbose,
					)
				else:
					raise ValueError("Provide either quantity, notional_usdt, or risk_percent_of_bank (with or without current_bank_usdt)")

			# 4) Compute entry limit price by deviation
			if side.upper() == "BUY":
				limit_price_raw = entry_price * (1.0 - deviation_percent / 100.0)
			elif side.upper() == "SELL":
				limit_price_raw = entry_price * (1.0 + deviation_percent / 100.0)
			else:
				raise ValueError("side must be 'BUY' or 'SELL'")

			limit_price = self._round_price(limit_price_raw, tick_size)
			qty_rounded = self._round_qty(quantity, step_size, min_qty)
			# Prepare strings according to Binance steps
			tick_size_str = str(pf.get("tickSize", "0.0001"))
			step_size_str = str(ls.get("stepSize", "1"))
			limit_price_str = self._format_by_step(limit_price, tick_size_str)
			qty_str = self._format_by_step(qty_rounded, step_size_str)
			self._log(verbose, "Computed entry and quantity", {
				"limit_price_raw": limit_price_raw,
				"limit_price": limit_price_str,
				"quantity_raw": quantity,
				"quantity": qty_str,
			})

			# 5) Validate lot size and notional
			self._validate_qty_notional(price=float(limit_price_str) if limit_price_str else entry_price, qty=float(qty_str), min_qty=min_qty, min_notional=min_notional)
			self._log(verbose, "Validation passed", {"notional": (float(limit_price_str) if limit_price_str else entry_price) * float(qty_str)})

			# 6) Place entry LIMIT order
			entry_order = self.client.new_order(
				symbol=symbol,
				side=side.upper(),
				type="LIMIT",
				timeInForce=time_in_force,
				quantity=qty_str,
				price=limit_price_str,
				positionSide=position_side,
				recvWindow=self.recv_window_ms,
			)
			orders_raw["entry"] = entry_order
			self._log(verbose, "Entry order placed", {"orderId": entry_order.get("orderId"), "price": limit_price_str, "qty": qty_str, "response": entry_order})

			# 7) Place Stop-Loss (STOP_MARKET reduceOnly)
			stop_price = self._round_price(stop_loss_price, tick_size)
			stop_price_str = self._format_by_step(stop_price, tick_size_str)
			stop_order = self.client.new_order(
				symbol=symbol,
				side=("SELL" if side.upper() == "BUY" else "BUY"),
				type="STOP_MARKET",
				stopPrice=stop_price_str,
				closePosition=False,
				reduceOnly=reduce_only,
				workingType=working_type,
				quantity=qty_str,
				positionSide=position_side,
				recvWindow=self.recv_window_ms,
			)
			orders_raw["stop"] = stop_order
			self._log(verbose, "Stop-loss order placed", {"orderId": stop_order.get("orderId"), "stopPrice": stop_price_str, "response": stop_order})

			# 8) Optional Take-Profit (TAKE_PROFIT_MARKET reduceOnly)
			take_profit_order = None
			if take_profit_price is not None:
				tp_price = self._round_price(float(take_profit_price), tick_size)
				tp_price_str = self._format_by_step(tp_price, tick_size_str)
				take_profit_order = self.client.new_order(
					symbol=symbol,
					side=("SELL" if side.upper() == "BUY" else "BUY"),
					type="TAKE_PROFIT_MARKET",
					stopPrice=tp_price_str,
					closePosition=False,
					reduceOnly=reduce_only,
					workingType=working_type,
					quantity=qty_str,
					positionSide=position_side,
					recvWindow=self.recv_window_ms,
				)
				orders_raw["take_profit"] = take_profit_order
				self._log(verbose, "Take-profit order placed", {"orderId": take_profit_order.get("orderId"), "tpPrice": tp_price_str, "response": take_profit_order})

			# 9) Trailing Stop (TRAILING_STOP_MARKET)
			activation = self._round_price(trailing_activation_price, tick_size)
			activation_str = self._format_by_step(activation, tick_size_str)
			callback = self._clamp_callback_rate(trailing_callback_percent)
			# One decimal step for callbackRate
			callback_str = format((Decimal(str(callback)).quantize(Decimal('0.1'), rounding=ROUND_DOWN)), 'f')
			# Try to fetch current mark price for diagnostics
			mark_price_val: Optional[float] = None
			try:
				mp = self.client.mark_price(symbol=symbol)
				# UMFutures.mark_price returns {"symbol":"ETHUSDT","markPrice":"...", ...}
				mark_price_val = float(mp.get("markPrice")) if isinstance(mp, dict) else None
			except Exception:
				mark_price_val = None
			# Log trailing diagnostics
			self._log(verbose, "Trailing params", {
				"side": ("SELL" if side.upper() == "BUY" else "BUY"),
				"activation": activation_str,
				"callbackRate": callback_str,
				"markPrice": mark_price_val,
			})
			trailing_stop_payload = {
				"symbol": symbol,
				"side": ("SELL" if side.upper() == "BUY" else "BUY"),
				"type": "TRAILING_STOP_MARKET",
				"activationPrice": activation_str,
				"callbackRate": callback_str,
				"positionSide": position_side,
				"recvWindow": self.recv_window_ms,
			}
			# choose sizing mode
			trailing_stop_payload["quantity"] = qty_str
			trailing_stop_payload["reduceOnly"] = reduce_only
			# Log final payload (without secrets)
			self._log(verbose, "Trailing payload", trailing_stop_payload)
			trailing_stop_order = None
			try:
				trailing_stop_order = self.client.new_order(**trailing_stop_payload)
				orders_raw["trailing_stop"] = trailing_stop_order
				self._log(verbose, "Trailing-stop order placed", {"orderId": trailing_stop_order.get("orderId"), "response": trailing_stop_order})
			except Exception as te:
				# Non-fatal: keep entry and stop orders active; report in logs
				self._log(True, "Trailing order failed (non-fatal)", {"error": str(te)})

			return OrderResult(
				success=True,
				message="Orders placed successfully",
				error_code=None,
				entry_order=entry_order,
				stop_order=stop_order,
				take_profit_order=take_profit_order,
				trailing_stop_order=trailing_stop_order,
				raw=orders_raw,
			)

		except Exception as e:
			code: Optional[int] = None
			msg: str = str(e)
			if isinstance(e, ClientError):
				code = getattr(e, "error_code", None) or getattr(e, "status_code", None)
				msg = getattr(e, "error_message", None) or msg
			self._log(True, "Order placement failed", {"error_code": code, "message": msg})
			return OrderResult(
				success=False,
				message=msg,
				error_code=code,
				entry_order=None,
				stop_order=None,
				take_profit_order=None,
				trailing_stop_order=None,
				raw=orders_raw,
			) 

	# -------- Helpers to (re)place trailing only --------
	def place_trailing_reduce_only(
		self,
		*,
		symbol: str,
		side: str,
		activation_price: float,
		callback_percent: float,
		quantity: float,
		position_side: str = "BOTH",
		reduce_only: bool = True,
		working_type: str = "MARK_PRICE",
		verbose: bool = True,
	) -> bool:
		try:
			# Load filters for formatting
			symbol_info = self._get_symbol_info(symbol)
			filters = self._get_filters(symbol_info)
			pf = filters.get("PRICE_FILTER", {})
			ls = filters.get("LOT_SIZE", {})
			tick_size_str = str(pf.get("tickSize", "0.0001"))
			step_size_str = str(ls.get("stepSize", "1"))
			activation_str = self._format_by_step(self._round_price(float(activation_price), float(pf.get("tickSize", 0.0)) or 0.0), tick_size_str)
			qty_str = self._format_by_step(self._round_qty(float(quantity), float(ls.get("stepSize", 0.0)) or 0.0, float(ls.get("minQty", 0.0)) or 0.0), step_size_str)
			callback = self._clamp_callback_rate(callback_percent)
			callback_str = format((Decimal(str(callback)).quantize(Decimal('0.1'), rounding=ROUND_DOWN)), 'f')
			payload = {
				"symbol": symbol,
				"side": side.upper(),
				"type": "TRAILING_STOP_MARKET",
				"activationPrice": activation_str,
				"callbackRate": callback_str,
				"positionSide": position_side,
				"recvWindow": self.recv_window_ms,
				"quantity": qty_str,
				"reduceOnly": reduce_only,
			}
			self._log(verbose, "Trailing (re)place payload", payload)
			resp = self.client.new_order(**payload)
			self._log(verbose, "Trailing (re)placed", {"orderId": resp.get("orderId"), "response": resp})
			return True
		except Exception as e:
			self._log(True, "Trailing (re)place failed", {"symbol": symbol, "error": str(e)})
			return False