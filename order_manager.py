from __future__ import annotations

import time
import threading
import json
from datetime import datetime
from typing import Dict, Any, Optional
from decimal import Decimal, ROUND_DOWN

from binance_connector import BaseFuturesConnector


class OrderManager:
	def __init__(self, connector: BaseFuturesConnector, config: Dict[str, Any]) -> None:
		self.cx = connector
		self.cfg = config or {}
		self.om = self.cfg.get("order_manager", {})
		self.deal = self.cfg.get("deal_config", {})
		self.retries = int(self.om.get("retries", 3))
		self.backoff = list(self.om.get("backoff_sec", [0.5, 1, 2]))
		self.placement_timeout = float(self.om.get("placement_timeout_sec", 15))
		self.max_slippage_pct = float(self.om.get("max_slippage_pct", 0.3))
		self.entry_ttl_sec = int(self.om.get("unfilled_entry_ttl_sec", 20))
		self.log_enabled = bool(self.cfg.get("general", {}).get("enable_trade_calc_logging", True))
		self._locks: Dict[str, threading.Lock] = {}

	def _log(self, event: str, details: Dict[str, Any] = None) -> None:
		if not self.log_enabled:
			return
		rec = {"ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), "event": event, "details": details or {}}
		try:
			print("[OM] " + json.dumps(rec, ensure_ascii=False))
		except Exception:
			pass

	def _lock_for(self, symbol: str) -> threading.Lock:
		if symbol not in self._locks:
			self._locks[symbol] = threading.Lock()
		return self._locks[symbol]

	def _slippage_ok(self, symbol: str, planned_entry: float) -> bool:
		mp = self.cx.get_mark_price(symbol)
		if mp is None:
			return True
		delta = abs(mp - planned_entry) / planned_entry * 100.0
		return delta <= self.max_slippage_pct

	def _round_price(self, symbol: str, price: float) -> str:
		try:
			return self.cx.round_price(symbol, price)
		except Exception:
			# fallback 2 decimals
			return format(Decimal(str(price)).quantize(Decimal('0.01'), rounding=ROUND_DOWN), 'f')

	def _round_qty(self, symbol: str, qty: float) -> str:
		try:
			return self.cx.round_qty(symbol, qty)
		except Exception:
			return format(Decimal(str(qty)).quantize(Decimal('0.000001'), rounding=ROUND_DOWN), 'f')

	def place_managed_trade(self,
		*,
		symbol: str,
		side: str,
		entry_price: float,
		deviation_percent: float,
		stop_loss_price: float,
		trailing_activation_price: float,
		trailing_callback_percent: float,
		position_side: str = "BOTH",
		working_type: str = "MARK_PRICE",
		time_in_force: str = "GTC",
		leverage: Optional[int] = None,
		quantity: Optional[float] = None,
		risk_percent_of_bank: Optional[float] = None,
		balance_type: str = "collateral",
	) -> Dict[str, Any]:
		lock = self._lock_for(symbol)
		if not lock.acquire(timeout=1):
			return {"success": False, "message": "symbol busy"}
		try:
			start_ts = time.time()
			attempt = 0
			errors: list = []
			order_side = side.upper()

			# compute qty if needed and validate
			if quantity is None and risk_percent_of_bank is not None:
				# Log bank and inputs for transparency
				try:
					bank_used = self.cx.get_usdt_balance(balance_type)
					delta_abs = abs(float(entry_price) - float(stop_loss_price))
					self._log("qty_calc_inputs", {
						"symbol": symbol,
						"balance_type": balance_type,
						"bank": bank_used,
						"risk_percent": risk_percent_of_bank,
						"entry": entry_price,
						"stop": stop_loss_price,
						"delta": delta_abs
					})
				except Exception:
					pass
				quantity = self.cx.compute_quantity_by_risk(symbol=symbol, entry_price=entry_price, stop_loss_price=stop_loss_price, risk_percent=risk_percent_of_bank, balance_type=balance_type)
			if quantity is None:
				raise ValueError("quantity or risk_percent_of_bank must be provided")

			# derive planned limit price by deviation_percent (percent value)
			if order_side == "BUY":
				planned_limit = entry_price * (1.0 - deviation_percent / 100.0)
			else:
				planned_limit = entry_price * (1.0 + deviation_percent / 100.0)

			if not self._slippage_ok(symbol, entry_price):
				return {"success": False, "message": "slippage too high"}

			# round price/qty for filters
			price_str = self._round_price(symbol, planned_limit)
			price_num = float(price_str)
			qty_str = self._round_qty(symbol, float(quantity or 0))
			qty_num = float(qty_str)

			# ensure minQty and minNotional are satisfied; bump qty if needed
			# Validate qty/minNotional; do NOT increase quantity to avoid risk change
			try:
				self.cx.validate_qty_notional(symbol, price_num, qty_num)
			except Exception as ve:
				self._log("qty_notional_invalid", {"symbol": symbol, "price": price_str, "qty": qty_str, "error": str(ve)})
				return {"success": False, "message": f"invalid qty/notional: {ve}"}

			# stop and trailing rounding
			stop_str_planned = self._round_price(symbol, stop_loss_price)
			trail_act_str_planned = self._round_price(symbol, trailing_activation_price)
			cb = max(0.1, min(5.0, round(float(trailing_callback_percent), 1)))
			cb_str = format(Decimal(str(cb)).quantize(Decimal('0.1'), rounding=ROUND_DOWN), 'f')

			entry_res = None
			stop_res = None
			trail_res = None

			opp_side = ("SELL" if order_side == "BUY" else "BUY")

			while attempt <= self.retries:
				try:
					# optionally set leverage for IM connectors
					if leverage:
						try:
							self.cx.set_leverage(symbol, leverage)
						except Exception:
							pass
					# PLACE ENTRY if not placed
					if entry_res is None:
						self._log("place_entry", {"symbol": symbol, "side": order_side, "price": price_str, "qty": qty_str})
						entry_res = self.cx.place_limit_entry(symbol=symbol, side=order_side, price=price_str, qty=qty_str, tif=time_in_force, position_side=position_side)
					# PLACE STOP if not placed
					if stop_res is None:
						self._log("place_stop", {"symbol": symbol, "side": opp_side, "stopPrice": stop_str_planned, "qty": qty_str})
						stop_res = self.cx.place_stop_loss(symbol=symbol, side=opp_side, stop_price=stop_str_planned, qty=qty_str, position_side=position_side, reduce_only=True, working_type=working_type, mode='auto')
					# PLACE TRAILING if not placed
					if trail_res is None:
						self._log("place_trailing", {"symbol": symbol, "side": opp_side, "activation": trail_act_str_planned, "callback": cb_str, "qty": qty_str})
						trail_res = self.cx.place_trailing(symbol=symbol, side=opp_side, activation_price=trail_act_str_planned, callback_rate=cb_str, qty=qty_str, position_side=position_side, reduce_only=True, working_type=working_type, mode='auto')

					return {"success": True, "orders": {"entry": entry_res, "stop": stop_res, "trailing": trail_res}}
				except Exception as e:
					errors.append(str(e))
					self._log("place_attempt_error", {"attempt": attempt, "error": str(e)})
				if attempt < len(self.backoff):
					time.sleep(self.backoff[attempt])
				attempt += 1
				if time.time() - start_ts > self.placement_timeout:
					break

			# if failed — best effort rollback entry and protections if no position
			try:
				pos = self.cx.get_position(symbol)
				qty_pos = abs(float((pos or {}).get("positionAmt", 0) or 0))
				if qty_pos == 0:
					self._log("rollback_cancel_all", {"symbol": symbol})
					self.cx.cancel_all_open_orders(symbol)
			except Exception:
				pass
			return {"success": False, "message": "; ".join(errors) or "placement failed"}
		finally:
			lock.release()

	def watch_and_cleanup(self, symbol: str) -> None:
		try:
			open_orders = self.cx.get_open_orders(symbol)
			pos = self.cx.get_position(symbol) or {}
			qty_abs = abs(float(pos.get("positionAmt", 0) or 0))
			entries = [o for o in open_orders if o.get("type") == "LIMIT"]
			protections = [o for o in open_orders if o.get("type") in ("STOP", "STOP_MARKET", "TRAILING_STOP_MARKET", "TAKE_PROFIT", "TAKE_PROFIT_MARKET")]

			# brief log of state
			self._log("cleanup_state", {"symbol": symbol, "open_orders": len(open_orders or []), "entries": len(entries), "protections": len(protections), "pos_abs": qty_abs})

			if qty_abs == 0:c
				# Evaluate TTL for entries (if any)
				now_ms = int(time.time() * 1000)
				def _ts(o: Dict[str, Any]) -> int:
					return int(o.get("time") or o.get("transactTime") or o.get("updateTime") or o.get("workingTime") or 0) or now_ms
				oldest = min((_ts(o) for o in entries), default=now_ms)
				expired = (self.entry_ttl_sec > 0) and ((now_ms - oldest) > self.entry_ttl_sec * 1000)
				# Rules when no position:
				# - If no entry but protections exist → stray protections → cancel
				# - If entry exists and TTL expired → cancel all (entry + protections)
				# - If entry exists and TTL not expired → keep both entry and protections
				if not entries and protections:
					self._log("cleanup_stray_protections", {"symbol": symbol, "count": len(protections)})
					self.cx.cancel_all_open_orders(symbol)
				elif entries and expired:
					self._log("entry_ttl_expired", {"symbol": symbol, "ttl": self.entry_ttl_sec, "entries": len(entries)})
					self.cx.cancel_all_open_orders(symbol)
				else:
					self._log("entry_alive_with_protections", {"symbol": symbol, "ttl": self.entry_ttl_sec, "entries": len(entries), "protections": len(protections)})
				return

			# position exists — ensure protections
			trail_present = any(o.get("type") == "TRAILING_STOP_MARKET" for o in protections)
			stop_present = any(o.get("type") in ("STOP", "STOP_MARKET", "TAKE_PROFIT", "TAKE_PROFIT_MARKET") for o in protections)
			if not (trail_present and stop_present):
				try:
					entry_price = float(pos.get("entryPrice", 0) or 0)
					qty_signed = float(pos.get("positionAmt", 0) or 0)
					qty_abs_s = format(Decimal(str(abs(qty_signed))).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN), 'f')
					if qty_abs <= 0 or entry_price <= 0:
						return
					opp_side = ("SELL" if qty_signed > 0 else "BUY")
					if not trail_present:
						# heuristic re-arm trailing
						act = entry_price * (1.003 if qty_signed > 0 else 0.997)
						cb = "0.5"
						self.cx.place_trailing(symbol=symbol, side=opp_side, activation_price=self._round_price(symbol, act), callback_rate=cb, qty=qty_abs_s, position_side="BOTH", reduce_only=True, working_type="MARK_PRICE", mode='auto')
					if not stop_present:
						# heuristic re-arm stop near entry ±0.5%
						stop_p = entry_price * (0.995 if qty_signed > 0 else 1.005)
						self.cx.place_stop_loss(symbol=symbol, side=opp_side, stop_price=self._round_price(symbol, stop_p), qty=qty_abs_s, position_side="BOTH", reduce_only=True, working_type="MARK_PRICE", mode='auto')
				except Exception as inner_ex:
					self._log("watch_cleanup_rearm_error", {"symbol": symbol, "error": str(inner_ex)})
					return
					return
		except Exception as e:
			self._log("watch_and_cleanup_error", {"symbol": symbol, "error": str(e)})
			return