#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

try:
	from user_data.credentials import (
		sub1_api_key_3 as API_KEY,
		sub1_api_secret_3 as API_SECRET,
	)
except Exception:
	API_KEY = ""
	API_SECRET = ""

from binance_connect import Binance_connect


def print_json(title: str, data: Any) -> None:
	try:
		print(f"\n=== {title} ===")
		print(json.dumps(data, ensure_ascii=False, indent=2))
	except Exception:
		print(f"\n=== {title} (raw) ===")
		print(str(data))


def test_balances(conn: Binance_connect) -> None:
	print("\n[Balances diagnostics]")
	# Primary PM account (UM)
	try:
		acc_um = conn._pm_request("GET", "/papi/v1/um/account", {})
		print_json("/papi/v1/um/account", acc_um)
	except Exception as ex:
		print("/papi/v1/um/account FAILED:", ex)
	# UM balances list
	try:
		bal_um = conn._pm_request("GET", "/papi/v1/um/balance", {})
		print_json("/papi/v1/um/balance", bal_um)
	except Exception as ex:
		print("/papi/v1/um/balance FAILED:", ex)
	# Generic PM account (aggregated collateral)
	try:
		acc_pm = conn._pm_request("GET", "/papi/v1/account", {})
		print_json("/papi/v1/account", acc_pm)
	except Exception as ex:
		print("/papi/v1/account FAILED:", ex)
	# Generic PM balance list
	try:
		bal_pm = conn._pm_request("GET", "/papi/v1/balance", {})
		print_json("/papi/v1/balance", bal_pm)
	except Exception as ex:
		print("/papi/v1/balance FAILED:", ex)
	# High-level helpers
	for bt in ("available", "wallet", "collateral"):
		try:
			val = conn.get_usdt_balance(balance_type=bt)
			print(f"get_usdt_balance({bt}) => {val}")
		except Exception as ex:
			print(f"get_usdt_balance({bt}) FAILED: {ex}")


def test_orders(conn: Binance_connect, symbol: str) -> None:
	print("\n[Orders diagnostics]")
	# List open orders
	try:
		open_all = conn._pm_request("GET", "/papi/v1/um/openOrders", {})
		print_json("openOrders (all)", open_all)
	except Exception as ex:
		print("openOrders(all) FAILED:", ex)
	try:
		open_sym = conn._pm_request("GET", "/papi/v1/um/openOrders", {"symbol": symbol})
		print_json(f"openOrders({symbol})", open_sym)
	except Exception as ex:
		print(f"openOrders({symbol}) FAILED:", ex)

	# Place and cancel a tiny test order flow (LIMIT only, no stop/tp), if desired
	# WARNING: uncomment only if you want real test placement
	# try:
	# 	res = conn._pm_request("POST", "/papi/v1/um/order", {
	# 		"symbol": symbol,
	# 		"side": "BUY",
	# 		"type": "LIMIT",
	# 		"timeInForce": "GTC",
	# 		"quantity": "0.001",
	# 		"price": "1",
	# 		"positionSide": "BOTH",
	# 	})
	# 	print_json("placed test order", res)
	# 	if isinstance(res, dict) and res.get("orderId"):
	# 		cancel = conn._pm_request("DELETE", "/papi/v1/um/order", {"symbol": symbol, "orderId": res.get("orderId")})
	# 		print_json("cancel test order", cancel)
	# except Exception as ex:
	# 	print("test order placement FAILED:", ex)


def main() -> int:
	parser = argparse.ArgumentParser(description="PAPI PM diagnostics")
	parser.add_argument("--symbol", default="BTCUSDT")
	parser.add_argument("--apiKey", default=API_KEY)
	parser.add_argument("--apiSecret", default=API_SECRET)
	args = parser.parse_args()

	if not args.apiKey or not args.apiSecret:
		print("Missing API key/secret. Fill user_data/credentials or pass --apiKey/--apiSecret")
		return 2

	conn = Binance_connect(
		api_key=args.apiKey,
		api_secret=args.apiSecret,
		api_mode="pm",
		log_to_file=True,
		log_file_path="logs/papi_pm_diag.log",
	)

	test_balances(conn)
	test_orders(conn, args.symbol)
	return 0


if __name__ == "__main__":
	sys.exit(main())

