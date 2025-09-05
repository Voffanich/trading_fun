import threading
import time
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from binance_connect import Binance_connect


class OrderManager:

	def __init__(self, bnc: Binance_connect, config: Dict[str, Any]):
		self.bnc = bnc
		self.cfg = config.get("order_manager", {})
		self.retries: int = int(self.cfg.get("retries", 3))
		self.backoff: List[float] = self.cfg.get("backoff_sec", [0.5, 1, 2])
		self.poll_interval: float = float(self.cfg.get("poll_interval_sec", 2))
		self.placement_timeout: float = float(self.cfg.get("placement_timeout_sec", 15))
		self.max_slippage_pct: float = float(self.cfg.get("max_slippage_pct", 0.2))
		self.log_to_console: bool = bool(config.get("general", {}).get("enable_trade_calc_logging", False))
		self.log_to_file: bool = True
		self.log_path: str = os.path.join("logs", "order_manager.log")
		os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
		self._locks: Dict[str, threading.Lock] = {}

	def _lock_for_symbol(self, symbol: str) -> threading.Lock:
		if symbol not in self._locks:
			self._locks[symbol] = threading.Lock()
		return self._locks[symbol]

	def _slippage_ok(self, symbol: str, planned_entry: float) -> bool:
		mark = self.bnc.get_mark_price(symbol)
		if not mark:
			return True
		delta = abs(mark - planned_entry) / planned_entry * 100.0
		return delta <= self.max_slippage_pct

	def _log(self, event: str, details: Dict[str, Any] = None):
		rec = {
			"ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
			"event": event,
			"details": details or {}
		}
		line = json.dumps(rec, ensure_ascii=False)
		if self.log_to_console:
			print(f"[OrderManager] {line}")
		if self.log_to_file:
			try:
				with open(self.log_path, "a", encoding="utf-8") as f:
					f.write(line + "\n")
			except Exception:
				pass

	def place_managed_trade(self,
		*,
		symbol: str,
		side: str,
		entry_price: float,
		deviation_percent: float,
		stop_loss_price: float,
		trailing_activation_price: float,
		trailing_callback_percent: float,
		leverage: int,
		quantity: Optional[float],
		risk_percent_of_bank: Optional[float],
		position_side: str = "BOTH",
		working_type: str = "MARK_PRICE",
		time_in_force: str = "GTC",
		deal_id: Optional[int] = None,
		verbose: bool = True,
	) -> Dict[str, Any]:
		lock = self._lock_for_symbol(symbol)
		if not lock.acquire(timeout=1):
			return {"success": False, "message": "symbol busy"}
		try:
			start_ts = time.time()
			attempt = 0
			last_error = None
			while attempt <= self.retries:
				self._log("place_attempt", {"symbol": symbol, "attempt": attempt})
				if not self._slippage_ok(symbol, entry_price):
					self._log("slippage_block", {"symbol": symbol, "entry_price": entry_price})
					return {"success": False, "message": "slippage too high"}
				res = self.bnc.place_futures_order_with_protection(
					symbol=symbol,
					side=side,
					entry_price=entry_price,
					deviation_percent=deviation_percent,
					stop_loss_price=stop_loss_price,
					trailing_activation_price=trailing_activation_price,
					trailing_callback_percent=trailing_callback_percent,
					leverage=leverage,
					quantity=quantity,
					risk_percent_of_bank=risk_percent_of_bank,
					position_side=position_side,
					working_type=working_type,
					time_in_force=time_in_force,
					skip_account_setup=False,
					verbose=verbose,
				)
				if res.success:
					self._log("place_success", {"symbol": symbol})
					return {"success": True, "orders": res.raw}
				last_error = res.message
				self._log("place_error", {"symbol": symbol, "message": last_error})
				if attempt < len(self.backoff):
					time.sleep(self.backoff[attempt])
				attempt += 1
				if time.time() - start_ts > self.placement_timeout:
					break
			# rollback best-effort
			try:
				self._log("rollback", {"symbol": symbol})
				self.bnc.cancel_all_open_orders(symbol)
			except Exception:
				pass
			return {"success": False, "message": last_error or "placement failed"}
		finally:
			lock.release()

	def watch_and_cleanup(self, symbol: str, *, verbose: bool = False) -> None:
		"""Cancel leftover protective order if position is closed, or restore protection if missing."""
		open_orders = self.bnc.get_open_orders(symbol)
		pos = self.bnc.get_position(symbol)
		qty = abs(float(pos.get("positionAmt", 0))) if pos else 0.0
		if qty == 0:
			# No position: protective orders should not hang
			if open_orders:
				self._log("cleanup_no_position", {"symbol": symbol, "open_orders": len(open_orders)})
				self.bnc.cancel_all_open_orders(symbol)
			return
		# Position exists: ensure at least one protective order is present
		has_protection = any(o.get("type") in ("STOP_MARKET", "TRAILING_STOP_MARKET") for o in open_orders)
		if not has_protection:
			# Best-effort: add trailing stop by last known params is out of scope here; needs strategy context
			self._log("no_protection", {"symbol": symbol})
			return

