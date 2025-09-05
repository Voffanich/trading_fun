#!/usr/bin/env python
from __future__ import annotations

import json
from typing import Optional

try:
	from user_data.credentials import sub1_api_key, sub1_api_secret
except Exception:
	sub1_api_key = None
	sub1_api_secret = None

from binance_connect import Binance_connect


# ==============================
# Simple inline configuration
# ==============================
CONFIG = {
	"api_key": sub1_api_key or "",            # or put your key string here
	"api_secret": sub1_api_secret or "",      # or put your secret string here
	"testnet": False,                           # set False for production
	"log_to_file": True,                       # write JSONL logs to logs/binance_connector.log
	"log_file_path": None,                     # or custom path, e.g. "logs/my_orders.log"
	"skip_account_setup": False,                # do not change margin type/leverage inside connector
	"verbose": True,                           # console verbose logs

	# Trade parameters
	"symbol": "ETHUSDT",
	"side": "BUY",                            # BUY or SELL
	"entry_price": 3500.0,                    # reference entry price
	"deviation_percent": 0.1,                 # limit offset from entry price (%)
	"stop_loss_price": 3450.0,                # stop-loss trigger price
	"trailing_activation_price": 3520.0,      # trailing activation price
	"trailing_callback_percent": 0.5,         # trailing callback percent (0.1..5)
	"leverage": 10,                            # leverage
	"margin_type": "ISOLATED",               # ISOLATED or CROSSED
	"position_side": "BOTH",                 # BOTH for one-way
	"working_type": "MARK_PRICE",            # MARK_PRICE or CONTRACT_PRICE
	"time_in_force": "GTC",                  # GTC, IOC, FOK
	"take_profit_price": None,                # optional TP trigger price

	# Sizing (choose ONE of quantity | notional_usdt | risk_percent_of_bank)
	"quantity": None,
	"notional_usdt": None,
	"risk_percent_of_bank": 3.0,
	"current_bank_usdt": None,
}


def main() -> int:
	api_key = (CONFIG["api_key"] or "").strip()
	api_secret = (CONFIG["api_secret"] or "").strip()
	if not api_key or not api_secret:
		print("API key/secret are missing. Fill CONFIG['api_key'] and CONFIG['api_secret'] or user_data.credentials.")
		return 2

	conn = Binance_connect(
		api_key=api_key,
		api_secret=api_secret,
		testnet=bool(CONFIG.get("testnet", False)),
		recv_window_ms=60000,
		log_to_file=bool(CONFIG.get("log_to_file", False)),
		log_file_path=CONFIG.get("log_file_path"),
	)

	result = conn.place_futures_order_with_protection(
		symbol=CONFIG["symbol"],
		side=str(CONFIG["side"]).upper(),
		entry_price=float(CONFIG["entry_price"]),
		deviation_percent=float(CONFIG["deviation_percent"]),
		stop_loss_price=float(CONFIG["stop_loss_price"]),
		trailing_activation_price=float(CONFIG["trailing_activation_price"]),
		trailing_callback_percent=float(CONFIG["trailing_callback_percent"]),
		leverage=int(CONFIG["leverage"]),
		quantity=CONFIG.get("quantity"),
		notional_usdt=CONFIG.get("notional_usdt"),
		risk_percent_of_bank=CONFIG.get("risk_percent_of_bank"),
		current_bank_usdt=CONFIG.get("current_bank_usdt"),
		take_profit_price=CONFIG.get("take_profit_price"),
		margin_type=str(CONFIG["margin_type"]),
		reduce_only=True,
		working_type=str(CONFIG["working_type"]),
		time_in_force=str(CONFIG["time_in_force"]),
		position_side=str(CONFIG["position_side"]),
		skip_account_setup=bool(CONFIG.get("skip_account_setup", False)),
		verbose=bool(CONFIG.get("verbose", False)),
	)

	print("Success:", result.success)
	print("Message:", result.message)
	print("Error code:", result.error_code)
	print("Entry order:", json.dumps(result.entry_order or {}, ensure_ascii=False))
	print("Stop order:", json.dumps(result.stop_order or {}, ensure_ascii=False))
	print("TP order:", json.dumps(result.take_profit_order or {}, ensure_ascii=False))
	print("Trailing order:", json.dumps(result.trailing_stop_order or {}, ensure_ascii=False))
	return 0 if result.success else 1


if __name__ == "__main__":
	exit(main()) 