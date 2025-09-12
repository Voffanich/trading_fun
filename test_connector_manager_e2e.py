#!/usr/bin/env python
from __future__ import annotations

import os
import time
from typing import Dict, Any, Optional

from binance_connector import ClassicIMConnector, PortfolioPMConnector, BaseFuturesConnector
from order_manager import OrderManager
from user_data.credentials import apikey3, sub1_api_key_3, sub1_api_secret_3

# ==============================
# Inline configuration
# ==============================
CONFIG: Dict[str, Any] = {
	"general": {
		"futures_api_mode": os.environ.get("FUTURES_API_MODE", "pm"),  # "classic" | "pm"
		"testnet": bool(int(os.environ.get("BINANCE_TESTNET", "0"))),
		"enable_trade_calc_logging": True,
		"recv_window_ms": 60000,
	},
	"order_manager": {
		"retries": 2,
		"backoff_sec": [0.5, 1.0],
		"placement_timeout_sec": 20,
		"max_slippage_pct": 0.5,
		"unfilled_entry_ttl_sec": 20,
	},
	"deal_config": {
		"working_type": "MARK_PRICE",
		"time_in_force": "GTC",
		"trailing_callback_percent": 0.5,
	},
	"tests": {
		"balances": True,
		"limit_entry": True,
		"stop_market": True,
		"trailing": True,
		"managed_trade": False,
		"cleanup": True,
	}
}

# API keys (env or inline here)
API_KEY = sub1_api_key_3
API_SECRET = sub1_api_secret_3

# Test parameters (env override)
SYMBOL = os.environ.get("TEST_SYMBOL", "ETHUSDT").strip()
SIDE = os.environ.get("TEST_SIDE", "BUY").strip()
ENTRY_PRICE = float(os.environ.get("TEST_ENTRY_PRICE", "4300"))
DEVIATION_PCT = float(os.environ.get("TEST_DEVIATION_PCT", "0.00"))
STOP_LOSS_PRICE = float(os.environ.get("TEST_STOP_LOSS", "4320"))
TRAIL_ACTIVATION = float(os.environ.get("TEST_TRAIL_ACT", "4380"))
TRAIL_CB = float(os.environ.get("TEST_TRAIL_CB", "0.5"))
POSITION_SIDE = os.environ.get("TEST_POSITION_SIDE", "BOTH").strip()
TIF = CONFIG["deal_config"]["time_in_force"]
WORKING_TYPE = CONFIG["deal_config"]["working_type"]
RISK_PCT = float(os.environ.get("TEST_RISK_PCT", "1.0"))
EXPLICIT_QTY = os.environ.get("TEST_QTY", "")


def _print_header(title: str) -> None:
	print("\n" + "=" * 80)
	print(title)
	print("=" * 80)


def init_connector() -> BaseFuturesConnector:
	mode = CONFIG["general"]["futures_api_mode"].lower()
	testnet = bool(CONFIG["general"]["testnet"])
	recv = int(CONFIG["general"]["recv_window_ms"])
	if mode == "classic":
		cx = ClassicIMConnector(api_key=API_KEY, api_secret=API_SECRET, testnet=testnet, recv_window_ms=recv, log=True)
	else:
		# PM with conditional default on
		cx = PortfolioPMConnector(api_key=API_KEY, api_secret=API_SECRET, testnet=testnet, recv_window_ms=recv, log=True, use_conditional=True, strategy_type="1")
	return cx


def test_balances(cx: BaseFuturesConnector) -> None:
	_print_header("Balances")
	for kind in ("available", "wallet", "collateral"):
		try:
			val = cx.get_usdt_balance(balance_type=kind)
			print(f"{kind}: {val}")
		except Exception as e:
			print(f"{kind}: ERROR {e}")


def test_limit_entry(cx: BaseFuturesConnector, side: str) -> Optional[dict]:
	_print_header(f"LIMIT entry {side}")
	filters = cx.get_filters(SYMBOL)
	# compute planned limit
	if side.upper() == "BUY":
		planned = ENTRY_PRICE * (1.0 - DEVIATION_PCT / 100.0)
	else:
		planned = ENTRY_PRICE * (1.0 + DEVIATION_PCT / 100.0)
	price_str = cx.round_price(SYMBOL, planned)
	qty: Optional[str]
	if EXPLICIT_QTY.strip():
		qty = cx.round_qty(SYMBOL, float(EXPLICIT_QTY))
	else:
		q = cx.compute_quantity_by_risk(SYMBOL, ENTRY_PRICE, STOP_LOSS_PRICE, RISK_PCT, balance_type="available")
		qty = cx.round_qty(SYMBOL, q)
	res = cx.place_limit_entry(SYMBOL, side.upper(), price_str, qty, TIF, POSITION_SIDE)
	print("entry:", res)
	return res


def test_stop_market(cx: BaseFuturesConnector, *, opp_side: str, qty: str) -> None:
	_print_header(f"STOP reduceOnly {opp_side}")
	stop_str = cx.round_price(SYMBOL, STOP_LOSS_PRICE)
	resp = cx.place_stop_loss(SYMBOL, opp_side, stop_str, qty, POSITION_SIDE, True, WORKING_TYPE, mode='auto')
	print("stop:", resp)


def test_trailing(cx: BaseFuturesConnector, *, opp_side: str, qty: str) -> None:
	_print_header(f"TRAILING {opp_side}")
	act_str = cx.round_price(SYMBOL, TRAIL_ACTIVATION)
	cb = max(0.1, min(5.0, round(float(TRAIL_CB), 1)))
	cb_str = str(cb)
	resp = cx.place_trailing(SYMBOL, opp_side, act_str, cb_str, qty, POSITION_SIDE, True, WORKING_TYPE, mode='auto')
	print("trailing:", resp)


def test_managed_trade(cx: BaseFuturesConnector) -> None:
	_print_header("Managed trade (entry + stop + trailing)")
	om = OrderManager(cx, CONFIG)
	res = om.place_managed_trade(symbol=SYMBOL, side=SIDE, entry_price=ENTRY_PRICE, deviation_percent=DEVIATION_PCT, stop_loss_price=STOP_LOSS_PRICE, trailing_activation_price=TRAIL_ACTIVATION, trailing_callback_percent=TRAIL_CB, position_side=POSITION_SIDE, working_type=WORKING_TYPE, time_in_force=TIF, leverage=None, quantity=(float(EXPLICIT_QTY) if EXPLICIT_QTY.strip() else None), risk_percent_of_bank=(None if EXPLICIT_QTY.strip() else RISK_PCT), balance_type="available")
	print("managed:", res)


def cleanup(cx: BaseFuturesConnector) -> None:
	_print_header("Cleanup open orders (symbol)")
	try:
		cx.cancel_all_open_orders(SYMBOL)
		print("cleanup: ok")
	except Exception as e:
		print("cleanup: ERROR", e)


def main() -> int:
	if not API_KEY or not API_SECRET:
		print("ERROR: set BINANCE_API_KEY and BINANCE_API_SECRET")
		return 2
	cx = init_connector()
	print("Mode:", CONFIG["general"]["futures_api_mode"], "Testnet:", CONFIG["general"]["testnet"])

	tog = CONFIG["tests"]
	if tog.get("balances"):
		test_balances(cx)

	entry = None
	qty_for_prot: Optional[str] = None
	if tog.get("limit_entry"):
		entry = test_limit_entry(cx, SIDE)
		# derive qty for protections
		try:
			orig = (entry or {}).get("origQty") or (entry or {}).get("quantity")
			qty_for_prot = str(orig) if orig is not None else None
		except Exception:
			qty_for_prot = None
		# small delay
		time.sleep(0.5)

	if tog.get("stop_market") and qty_for_prot:
		opp = ("SELL" if SIDE.upper() == "BUY" else "BUY")
		test_stop_market(cx, opp_side=opp, qty=qty_for_prot)
		time.sleep(0.5)

	if tog.get("trailing") and qty_for_prot:
		opp = ("SELL" if SIDE.upper() == "BUY" else "BUY")
		test_trailing(cx, opp_side=opp, qty=qty_for_prot)

	if tog.get("managed_trade"):
		test_managed_trade(cx)

	if tog.get("cleanup"):
		cleanup(cx)

	print("Done.")
	return 0


if __name__ == "__main__":
	exit(main()) 