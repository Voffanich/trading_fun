#!/usr/bin/env python
"""
Test: Cancel and restore open orders on Binance Portfolio Margin (PAPI)
- Prints positions and open orders (standard + conditional)
- Cancels all open orders on the configured symbol
- Verifies closure
- Re-creates the same orders with preserved parameters
"""

import time
import hmac
import hashlib
from typing import Dict, Any, List
from urllib.parse import urlencode, quote
import requests

# ==============================
# CONFIG (edit here)
# ==============================
CONFIG: Dict[str, Any] = {
	"api": {
		"base_url": "https://papi.binance.com",
		"recv_window": 5000,
	},
	"trade": {
		"symbol": "ETHUSDT",
		"position_side": "BOTH",
		"working_type": "MARK_PRICE",
		"reduce_only": "true",
		"price_protect": "false",
		"time_in_force": "GTC",
	},
}

# ==============================
# AUTH (import keys)
# ==============================
from user_data.credentials import sub1_api_key_3, sub1_api_secret_3
API_KEY = sub1_api_key_3
API_SECRET = sub1_api_secret_3

# ==============================
# Helpers
# ==============================

def _headers() -> dict:
	return {
		"X-MBX-APIKEY": API_KEY,
		"X-MBX-PORTFOLIO-MARGIN": "true",
		"Content-Type": "application/x-www-form-urlencoded",
	}


def _sign(payload: str) -> str:
	return hmac.new(API_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _ts() -> int:
	return int(time.time() * 1000)


def _get(path: str, params: Dict[str, Any]) -> Any:
	p = dict(params)
	p.setdefault("recvWindow", CONFIG["api"]["recv_window"])
	p.setdefault("timestamp", _ts())
	query = urlencode(sorted([(k, p[k]) for k in p.keys() if p[k] is not None]), doseq=True, quote_via=quote)
	sig = _sign(query)
	url = f"{CONFIG['api']['base_url']}{path}?{query}&signature={sig}"
	r = requests.get(url, headers=_headers())
	return r.json() if r.status_code < 400 else {"status": r.status_code, "error": r.text}


def _delete(path: str, params: Dict[str, Any]) -> Any:
	p = dict(params)
	p.setdefault("recvWindow", CONFIG["api"]["recv_window"])
	p.setdefault("timestamp", _ts())
	query = urlencode(sorted([(k, p[k]) for k in p.keys() if p[k] is not None]), doseq=True, quote_via=quote)
	sig = _sign(query)
	url = f"{CONFIG['api']['base_url']}{path}?{query}&signature={sig}"
	r = requests.delete(url, headers=_headers())
	return r.json() if r.status_code < 400 else {"status": r.status_code, "error": r.text}


def _post_order_query(path: str, params: Dict[str, Any]) -> Any:
	# For standard orders: params in query; sign query; empty body
	p = dict(params)
	p.setdefault("recvWindow", CONFIG["api"]["recv_window"])
	p.setdefault("timestamp", _ts())
	query = urlencode(sorted([(k, p[k]) for k in p.keys() if p[k] is not None]), doseq=True, quote_via=quote)
	sig = _sign(query)
	url = f"{CONFIG['api']['base_url']}{path}?{query}&signature={sig}"
	r = requests.post(url, headers=_headers(), data="")
	return r.json() if r.status_code < 400 else {"status": r.status_code, "error": r.text}


def _post_conditional_body(path: str, body: Dict[str, Any]) -> Any:
	# For conditional orders: body-signed; signature in query only
	b = dict(body)
	b.setdefault("recvWindow", CONFIG["api"]["recv_window"])
	b.setdefault("timestamp", _ts())
	b.setdefault("positionSide", CONFIG["trade"]["position_side"])
	b.setdefault("workingType", CONFIG["trade"]["working_type"])
	b.setdefault("reduceOnly", CONFIG["trade"]["reduce_only"])
	b.setdefault("priceProtect", CONFIG["trade"]["price_protect"])
	b.setdefault("strategyId", int(b["timestamp"]))
	body_str = urlencode(sorted([(k, b[k]) for k in b.keys() if b[k] is not None]), doseq=True, quote_via=quote)
	sig = _sign(body_str)
	url = f"{CONFIG['api']['base_url']}{path}?signature={sig}"
	r = requests.post(url, headers=_headers(), data=body_str)
	return r.json() if r.status_code < 400 else {"status": r.status_code, "error": r.text}

# ==============================
# Fetchers
# ==============================

def get_positions() -> Any:
	return _get("/papi/v1/um/account", {})


def get_open_orders(symbol: str) -> List[Dict[str, Any]]:
	resp = _get("/papi/v1/um/openOrders", {"symbol": symbol})
	return resp if isinstance(resp, list) else []


def get_open_conditional_orders(symbol: str) -> List[Dict[str, Any]]:
	# Try multiple endpoints as deployments differ
	resp = _get("/papi/v1/um/openConditionalOrders", {"symbol": symbol})
	if isinstance(resp, list):
		return resp
	resp2 = _get("/papi/v1/um/conditional/openOrders", {"symbol": symbol})
	if isinstance(resp2, list):
		return resp2
	return []

# ==============================
# Cancel helpers
# ==============================

def cancel_order(symbol: str, order_id: int) -> Any:
	return _delete("/papi/v1/um/order", {"symbol": symbol, "orderId": order_id})


def cancel_conditional(symbol: str, strategy_id: int = None, client_strategy_id: str = None) -> Any:
	# Try by numeric id first
	if strategy_id is not None:
		res = _delete("/papi/v1/um/conditional/order", {"symbol": symbol, "strategyId": strategy_id})
		# If API returns error, try by client strategy id
		if isinstance(res, dict) and res.get("status"):
			pass
		else:
			return res
	# Try by client id name used in docs as origClientStrategyId / newClientStrategyId
	if client_strategy_id:
		return _delete("/papi/v1/um/conditional/order", {"symbol": symbol, "origClientStrategyId": client_strategy_id})
	# As a last resort, bulk cancel
	return _delete("/papi/v1/um/conditional/allOpenOrders", {"symbol": symbol})

# ==============================
# Re-create helpers
# ==============================

def recreate_standard(order: Dict[str, Any]) -> Any:
	symbol = order["symbol"]
	side = order["side"]
	otype = order.get("type")
	qty = order.get("origQty") or order.get("quantity") or order.get("origQty", "")
	if otype == "LIMIT":
		params = {
			"symbol": symbol,
			"side": side,
			"type": "LIMIT",
			"timeInForce": order.get("timeInForce", CONFIG["trade"]["time_in_force"]),
			"quantity": qty,
			"price": order.get("price"),
			"positionSide": CONFIG["trade"]["position_side"],
		}
		return _post_order_query("/papi/v1/um/order", params)
	# Extend here if needed for other standard types
	return {"skipped": True, "reason": f"type {otype} not supported"}


def recreate_conditional(order: Dict[str, Any]) -> Any:
	symbol = order["symbol"]
	side = order["side"]
	otype = order.get("orderType") or order.get("type") or order.get("strategyType")
	qty = order.get("origQty") or order.get("quantity") or order.get("origQty", "")
	if otype == "STOP":
		body = {
			"symbol": symbol,
			"side": side,
			"orderType": "STOP",
			"strategyType": "STOP",
			"price": order.get("price") or order.get("origPrice") or order.get("stopPrice"),
			"stopPrice": order.get("stopPrice") or order.get("price"),
			"timeInForce": order.get("timeInForce", CONFIG["trade"]["time_in_force"]),
			"quantity": qty,
		}
		return _post_conditional_body("/papi/v1/um/conditional/order", body)
	if otype == "TAKE_PROFIT":
		body = {
			"symbol": symbol,
			"side": side,
			"orderType": "TAKE_PROFIT",
			"strategyType": "TAKE_PROFIT",
			"price": order.get("price") or order.get("origPrice") or order.get("stopPrice"),
			"stopPrice": order.get("stopPrice") or order.get("price"),
			"timeInForce": order.get("timeInForce", CONFIG["trade"]["time_in_force"]),
			"quantity": qty,
		}
		return _post_conditional_body("/papi/v1/um/conditional/order", body)
	if otype == "TRAILING_STOP_MARKET":
		body = {
			"symbol": symbol,
			"side": side,
			"orderType": "TRAILING_STOP_MARKET",
			"strategyType": "TRAILING_STOP_MARKET",
			"activationPrice": order.get("activationPrice") or order.get("activatePrice") or order.get("price"),
			"callbackRate": order.get("callbackRate") or order.get("priceRate") or "0.5",
			"quantity": qty,
		}
		return _post_conditional_body("/papi/v1/um/conditional/order", body)
	return {"skipped": True, "reason": f"cond type {otype} not supported"}

# ==============================
# Main flow
# ==============================

def main() -> None:
	symbol = CONFIG["trade"]["symbol"]
	print("Fetching positions...")
	positions = get_positions()
	print("POSITIONS:", positions)

	print("Fetching open standard orders...")
	std_orders = get_open_orders(symbol)
	print(f"STANDARD OPEN ORDERS ({len(std_orders)}):", std_orders)

	print("Fetching open conditional orders...")
	cond_orders = get_open_conditional_orders(symbol)
	print(f"CONDITIONAL OPEN ORDERS ({len(cond_orders)}):", cond_orders)

	# Preserve orders for restore
	std_snapshot = list(std_orders)
	cond_snapshot = list(cond_orders)

	print("Cancelling standard orders one-by-one...")
	for o in std_orders:
		try:
			resp = cancel_order(symbol, int(o.get("orderId")))
			print("CANCEL STD:", resp)
		except Exception as e:
			print("CANCEL STD ERROR:", str(e))

	print("Cancelling conditional orders one-by-one...")
	for o in cond_orders:
		try:
			sid = o.get("strategyId") or o.get("orderId")
			cid = o.get("newClientStrategyId") or o.get("origClientStrategyId")
			resp = cancel_conditional(symbol, int(sid) if sid else None, cid)
			print("CANCEL COND:", resp)
		except Exception as e:
			print("CANCEL COND ERROR:", str(e))

	print("Verifying closures...")
	after_std = get_open_orders(symbol)
	after_cond = get_open_conditional_orders(symbol)
	print(f"STANDARD OPEN NOW: {len(after_std)} | CONDITIONAL OPEN NOW: {len(after_cond)}")

	# If anything left, bulk-cancel conditionals
	if after_cond:
		print("Bulk-cancel any remaining conditional orders...")
		bulk = _delete("/papi/v1/um/conditional/allOpenOrders", {"symbol": symbol})
		print("BULK CANCEL COND:", bulk)

	print("Reopening preserved orders...")
	for o in std_snapshot:
		res = recreate_standard(o)
		print("REOPEN STD:", res)
	for o in cond_snapshot:
		res = recreate_conditional(o)
		print("REOPEN COND:", res)

	print("Done.")


if __name__ == "__main__":
	main() 