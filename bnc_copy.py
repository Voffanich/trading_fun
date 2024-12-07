from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException
import requests
import time
import hmac
import hashlib
import base64

from user_data.credentials import sub1_api_key, sub1_api_secret, sub1_account_email

class Binance_adapter():
    
    def __init__(self, api_key: str, api_secret: str, subaccount_email: str):
        self.API_KEY = api_key
        self.API_SECRET = api_secret
        self.SUBACCOUNT_EMAIL = subaccount_email
        self.BASE_URL = 'https://api.binance.com'
        # self.ENDPOINT = '/sapi/v1/sub-account/futures/account'
        # self.ENDPOINT = '/sapi/v1/sub-account/futures/assets'
        self.ENDPOINT = '/sapi/v1/sub-account/status'
        
        self.client = Client(self.API_KEY, self.API_SECRET)

    def get_balance(self):
        acc = self.client.get_margin_account()
        acc = self.client.futures_account()
        print(acc)
       
    
    def get_symbol_info(self, symbol):
        exchange_info = self.client.futures_exchange_info()
        return next((item for item in exchange_info['symbols'] if item['symbol'] == symbol), None)


    def calculate_trade_amount(self, balance, risk_percentage, entry_price, stop_loss_price, leverage, step_size):
        # Calculate maximum allowed loss
        max_loss_amount = balance * risk_percentage
        
        # Calculate potential loss per unit
        potential_loss_per_unit = abs(entry_price - stop_loss_price)
        
        # Determine trade amount based on max loss and leverage
        amount_to_trade = (max_loss_amount / potential_loss_per_unit) * leverage
        
        # Round down to nearest permissible lot size
        amount_to_trade -= amount_to_trade % step_size
        return amount_to_trade

    
   
# # Parameters
# trading_pair = 'BTCUSDT'
# risk_percentage_of_balance = 0.01  # 1% risk
# leverage = 10  # Example: 10x leverage

# try:
#     # Fetch account balance
#     balance_info = client.futures_account_balance()
#     usdt_balance = float(next(item for item in balance_info if item['asset'] == 'USDT')['balance'])
    
#     # Get current price as entry price for simplicity; replace with your logic as needed
#     entry_price = float(client.futures_symbol_ticker(symbol=trading_pair)['price'])
    
#     # Fetch symbol information for restrictions
#     symbol_info = get_symbol_info(client, trading_pair)
    
#     if not symbol_info:
#         raise ValueError("Symbol information could not be retrieved.")
    
#     min_qty = float(symbol_info['filters'][2]['minQty'])
#     step_size = float(symbol_info['filters'][2]['stepSize'])
    
#     client.futures_change_leverage(symbol=trading_pair, leverage=leverage)
    
#     # Long Trade Setup
#     stop_loss_long = entry_price * 0.98  # Set stop loss at 2% below entry for long
#     take_profit_long = entry_price * 1.05  # Set take profit at 5% above entry for long
    
#     amount_to_trade_long = calculate_trade_amount(
#         usdt_balance, risk_percentage_of_balance, entry_price, stop_loss_long, leverage, step_size)
    
#     # Ensure the trade amount is above the minimum order size
#     if amount_to_trade_long < min_qty:
#         raise ValueError(f"Calculated trade amount for long position ({amount_to_trade_long}) is below the minimum quantity ({min_qty}).")

#     order_long = client.futures_create_order(
#         symbol=trading_pair,
#         side=SIDE_BUY,
#         type=ORDER_TYPE_MARKET,
#         quantity=amount_to_trade_long,
#     )
#     print("Long market order placed:", order_long)

#     # OCO setup for Long position
#     oco_order_long = client.futures_oco_order(
#         symbol=trading_pair,
#         side=SIDE_SELL,
#         quantity=amount_to_trade_long,
#         price="{:.{precision}f}".format(take_profit_long, precision=symbol_info['pricePrecision']),
#         stopPrice="{:.{precision}f}".format(stop_loss_long, precision=symbol_info['pricePrecision']),
#         stopLimitPrice="{:.{precision}f}".format(stop_loss_long - 10, precision=symbol_info['pricePrecision']),
#         stopLimitTimeInForce='GTC',
#     )
#     print("OCO order placed for long position:", oco_order_long)

#     # Short Trade Setup
#     stop_loss_short = entry_price * 1.02  # Set stop loss at 2% above entry for short
#     take_profit_short = entry_price * 0.95  # Set take profit at 5% below entry for short

#     amount_to_trade_short = calculate_trade_amount(
#         usdt_balance, risk_percentage_of_balance, entry_price, stop_loss_short, leverage, step_size)

#     # Ensure the trade amount is above the minimum order size
#     if amount_to_trade_short < min_qty:
#         raise ValueError(f"Calculated trade amount for short position ({amount_to_trade_short}) is below the minimum quantity ({min_qty}).")

#     order_short = client.futures_create_order(
#         symbol=trading_pair,
#         side=SIDE_SELL,
#         type=ORDER_TYPE_MARKET,
#         quantity=amount_to_trade_short,
#     )
#     print("Short market order placed:", order_short)

#     # OCO setup for Short position 
#     oco_order_short = client.futures_oco_order(
#         symbol=trading_pair,
#         side=SIDE_BUY,
#         quantity=amount_to_trade_short,
#         price="{:.{precision}f}".format(take_profit_short, precision=symbol_info['pricePrecision']),
#         stopPrice="{:.{precision}f}".format(stop_loss_short, precision=symbol_info['pricePrecision']),
#         stopLimitPrice="{:.{precision}f}".format(stop_loss_short + 10, precision=symbol_info['pricePrecision']),
#         stopLimitTimeInForce='GTC',
#     )
#     print("OCO order placed for short position:", oco_order_short)

# except BinanceAPIException as e:
#     print(f"Binance API Exception: {e}")
# except BinanceOrderException as e:
#     print(f"Binance Order Exception: {e}")
# except Exception as e:
#     print(f"An unexpected error occurred: {e}")
    
    
    
