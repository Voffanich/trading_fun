#!/usr/bin/env python
"""
Test: Simulate managed trade on Binance Portfolio Margin (PAPI)
- Places 3 orders: LIMIT entry, conditional STOP, conditional TRAILING_STOP_MARKET
- Computes levels from current mark price using inline CONFIG
- Uses working syntax for PAPI conditional orders:
  * POST /papi/v1/um/conditional/order with BODY form-encoded
  * signature is HMAC over the exact BODY; URL carries only ?signature=
"""

import time
import hmac
import hashlib
from typing import Dict, Any
from urllib.parse import urlencode, quote
import requests

# ==============================
# CONFIG (edit here)
# ==============================
CONFIG: Dict[str, Any] = {
	"api": {
		"base_url": "https://papi.binance.com",
		"fapi_base": "https://fapi.binance.com",  # for mark price
		"recv_window": 5000,
	},
	"auth": {
		# keys are imported from local user_data.credentials module
		"api_key_name": "sub1_api_key_3",
		"api_secret_name": "sub1_api_secret_3",
	},
	"trade": {
		"symbol": "ETHUSDT",
		"side": "BUY",              # entry side: BUY or SELL
		"quantity": "0.01",         # base asset qty
		# Entry level from mark price in bps (+ above mark for SELL, - below mark for BUY)
		"entry_offset_bps": 5,        # 5 bps = 0.05%
		# Stop distance from entry price in bps (for BUY stop below; for SELL stop above)
		"stop_offset_bps": 50,        # 50 bps = 0.50%
		# Trailing activation offset from current mark in bps
		"trailing_activation_bps": 30, # 0.30% away from mark in proper direction
		"trailing_callback_rate": "0.5",  # percent, 0.1 - 5.0 step 0.1
		"time_in_force": "GTC",
		"working_type": "MARK_PRICE",
		"position_side": "BOTH",
		"reduce_only": "true",
		"price_protect": "false",
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


def server_time() -> int:
	url = f"{CONFIG['api']['base_url']}/papi/v1/time"
	r = requests.get(url)
	r.raise_for_status()
	return int(r.json()["serverTime"])


def get_mark_price(symbol: str) -> float:
	url = f"{CONFIG['api']['fapi_base']}/fapi/v1/premiumIndex"
	r = requests.get(url, params={"symbol": symbol})
	r.raise_for_status()
	data = r.json()
	return float(data["markPrice"]) if isinstance(data, dict) else float(data[0]["markPrice"])  # handle array edge case


def fmt_price(p: float) -> str:
	# Keep 2 decimals for majors like ETH; adjust if needed per filters in real bot
	return f"{p:.2f}"

# ==============================
# Placers
# ==============================

def place_entry_limit(symbol: str, side: str, price: str, qty: str, tif: str) -> dict:
	# Standard PAPI UM order (non-conditional). Send all in query; sign query.
	base = CONFIG["api"]["base_url"]
	params = {
		"symbol": symbol,
		"side": side,
		"type": "LIMIT",
		"timeInForce": tif,
		"quantity": qty,
		"price": price,
		"recvWindow": CONFIG["api"]["recv_window"],
		"timestamp": server_time(),
		"positionSide": CONFIG["trade"]["position_side"],
	}
	query = urlencode(sorted(params.items()), doseq=True, quote_via=quote)
	signature = _sign(query)
	url = f"{base}/papi/v1/um/order?{query}&signature={signature}"
	print("ENTRY URL:", url)
	r = requests.post(url, headers=_headers(), data="")
	return r.json() if r.status_code < 400 else {"status": r.status_code, "error": r.text}


def post_um_conditional(body: dict) -> dict:
	# Conditional: send all form fields in BODY; signature over BODY; only signature in query
	base = CONFIG["api"]["base_url"]
	b = dict(body)
	b.setdefault("recvWindow", CONFIG["api"]["recv_window"])
	b.setdefault("timestamp", server_time())
	b.setdefault("positionSide", CONFIG["trade"]["position_side"])
	b.setdefault("workingType", CONFIG["trade"]["working_type"])
	b.setdefault("reduceOnly", CONFIG["trade"]["reduce_only"])
	b.setdefault("priceProtect", CONFIG["trade"]["price_protect"])
	b.setdefault("strategyId", int(b["timestamp"]))
	body_sorted = sorted([(k, b[k]) for k in b.keys() if b[k] is not None])
	body_str = urlencode(body_sorted, doseq=True, quote_via=quote)
	signature = _sign(body_str)
	url = f"{base}/papi/v1/um/conditional/order?signature={signature}"
	print("COND URL:", url)
	print("COND SIGN BODY:", body_str)
	r = requests.post(url, headers=_headers(), data=body_str)
	return r.json() if r.status_code < 400 else {"status": r.status_code, "error": r.text}

# ==============================
# Scenario: compute levels and place 3 orders
# ==============================

def main() -> None:
	trade = CONFIG["trade"]
	symbol = trade["symbol"]
	side = trade["side"].upper()
	qty = trade["quantity"]
	mark = get_mark_price(symbol)
	print(f"MARK: {mark}")

	entry_offset = trade["entry_offset_bps"] / 10000.0
	stop_offset = trade["stop_offset_bps"] / 10000.0
	trail_act_bps = trade["trailing_activation_bps"] / 10000.0
	callback_rate = trade["trailing_callback_rate"]

	if side == "BUY":
		entry_price_f = mark * (1 - entry_offset)
		stop_price_f = entry_price_f * (1 - stop_offset)
		# SELL trailing for long protection: activation must be ABOVE latest price
		trail_activation_f = mark * (1 + trail_act_bps)
		prot_side = "SELL"
	else:
		entry_price_f = mark * (1 + entry_offset)
		stop_price_f = entry_price_f * (1 + stop_offset)
		# BUY trailing for short protection: activation must be BELOW latest price
		trail_activation_f = mark * (1 - trail_act_bps)
		prot_side = "BUY"

	entry_price = fmt_price(entry_price_f)
	stop_price = fmt_price(stop_price_f)
	trail_activation = fmt_price(trail_activation_f)

	print({
		"entry_price": entry_price,
		"stop_price": stop_price,
		"trail_activation": trail_activation,
		"callback_rate": callback_rate,
	})

	# 1) LIMIT entry
	entry_resp = place_entry_limit(
		symbol=symbol,
		side=side,
		price=entry_price,
		qty=qty,
		tif=trade["time_in_force"],
	)
	print("ENTRY response:", entry_resp)

	# 2) Conditional STOP (orderType=STOP, strategyType=STOP)
	stop_body = {
		"symbol": symbol,
		"side": prot_side,
		"orderType": "STOP",
		"strategyType": "STOP",
		"price": stop_price,
		"stopPrice": stop_price,
		"timeInForce": trade["time_in_force"],
		"quantity": qty,
	}
	stop_resp = post_um_conditional(stop_body)
	print("STOP response:", stop_resp)

	# 3) Conditional TRAILING_STOP_MARKET
	trail_body = {
		"symbol": symbol,
		"side": prot_side,
		"orderType": "TRAILING_STOP_MARKET",
		"strategyType": "TRAILING_STOP_MARKET",
		"activationPrice": trail_activation,
		"callbackRate": callback_rate,
		"quantity": qty,
	}
	trail_resp = post_um_conditional(trail_body)
	print("TRAIL response:", trail_resp)


if __name__ == "__main__":
	main() 
 