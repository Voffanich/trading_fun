#!/usr/bin/env python
"""
Binance Portfolio-Margin – «conditional» orders
STOP  &  TRAILING_STOP_MARKET  via  /papi/v1/um/conditional/order
"""

import time, hmac, hashlib, requests
from urllib.parse import urlencode, quote
from user_data.credentials import sub1_api_key_3, sub1_api_secret_3

# ---------------  конфиг  -----------------------	
API_KEY    = sub1_api_key_3
API_SECRET = sub1_api_secret_3
BASE_URL   = "https://papi.binance.com"

SYMBOL     = "ETHUSDT"
QUANTITY   = "0.01"
STOP_PRICE = "4220"
ACTIVATION_PRICE = "4220"
CALLBACK_RATE    = "0.5"

# ------------------------------------------------
def _headers():
	return {
		"X-MBX-APIKEY": API_KEY,
		"X-MBX-PORTFOLIO-MARGIN": "true",
		"Content-Type": "application/x-www-form-urlencoded"
	}

def _sign(raw: str) -> str:
	return hmac.new(API_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()


def server_time() -> int:
	return int(requests.get(f"{BASE_URL}/papi/v1/time").json()["serverTime"])


def post_um_conditional_body(params: dict):
	b = dict(params)
	b.setdefault("recvWindow", 5000)
	b.setdefault("timestamp", server_time())
	# Required/common fields
	b.setdefault("positionSide", "BOTH")
	b.setdefault("workingType", "MARK_PRICE")
	# DON'T set default strategyType here; it must be one of eligible strings per docs
	b.setdefault("strategyId", int(b["timestamp"]))
	# optional
	b.setdefault("reduceOnly", "true")
	b.setdefault("priceProtect", "false")
	# form-encode BODY in sorted key order
	body_sorted = sorted([(k, b[k]) for k in b.keys() if b[k] is not None])
	body_str = urlencode(body_sorted, doseq=True, quote_via=quote)
	signature = _sign(body_str)
	url = f"{BASE_URL}/papi/v1/um/conditional/order?signature={signature}"
	print("REQUEST URL:", url)
	print("SIGN BODY:", body_str)
	r = requests.post(url, headers=_headers(), data=body_str)
	return r.json() if r.status_code < 400 else {"status": r.status_code, "error": r.text}


# ----------------  examples  -------------------
if __name__ == "__main__":
	# 1) STOP (conditional) — requires price and stopPrice
	stop_resp = post_um_conditional_body({
		"symbol": SYMBOL,
		"side": "SELL",
		"orderType": "STOP",
		"strategyType": "STOP",
		"price": STOP_PRICE,
		"stopPrice": STOP_PRICE,
		"timeInForce": "GTC",
		"quantity": QUANTITY,
	})
	print("STOP  response:", stop_resp)

	# 2) TRAILING_STOP_MARKET — requires activationPrice and callbackRate
	trail_resp = post_um_conditional_body({
		"symbol": SYMBOL,
		"side": "SELL",
		"orderType": "TRAILING_STOP_MARKET",
		"strategyType": "TRAILING_STOP_MARKET",
		"activationPrice": ACTIVATION_PRICE,
		"callbackRate": CALLBACK_RATE,
		"quantity": QUANTITY,
	})
	print("TRAIL response:", trail_resp)