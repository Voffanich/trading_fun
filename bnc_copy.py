from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance.um_futures import UMFutures
from binance.lib.utils import config_logging
from binance.error import ClientError
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
                
        self.f_client = UMFutures(key = self.API_KEY, secret = self.API_SECRET)
        self.client = Client(self.API_KEY, self.API_SECRET)

    def get_balance_usdt(self):
        try:
            response = self.f_client.account()
            # print(response)
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
        
        try:    
            for asset in response['assets']:
                if asset['asset'] == 'USDT':
                    print(asset['asset'] + ' : ' + asset['walletBalance'])
                    return float(asset['walletBalance'])
        except error as error:
            print("Some fucking error happened. No USDT balance found")
            return False
            
    
    def set_leverage(self, pair, leverage):
        try:
            response = self.f_client.change_leverage(symbol=pair, leverage=leverage, recvWindow=6000)
            print(response)
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )    
        finally:
            return False
            
    def get_price_precision(self, pair):
        try:
            response = self.f_client.exchange_info()['symbols']
            for element in response:
                if element['symbol'] == pair:
                    print(f'Price presision for {pair} is {element["pricePrecision"]}')
                    return element['pricePrecision']
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
        finally:
            return False  
        
    
    def get_quantity_precision(self, pair):
        try:
            response = self.f_client.exchange_info()['symbols']
            for element in response:
                if element['symbol'] == pair:
                    print(f'Quantity presision for {pair} is {element["quantityPrecision"]}')
                    return element['quantityPrecision']
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
        finally:
            return False 
        
        
    def get_minimum_quantity(self, pair):
        try:
            response = self.f_client.exchange_info()['symbols']
            for element in response:
                if element['symbol'] == pair:
                    print(f'Minimum quantity for {pair} is {element["filters"][2]["minQty"]}')
                    return element['filters'][2]['minQty']
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
        finally:
            return False 
        
    
    def get_step_size(self, pair):
        try:
            response = self.f_client.exchange_info()['symbols']
            for element in response:
                if element['symbol'] == pair:
                    print(f'Step size for {pair} is {element["filters"][2]["stepSize"]}')
                    return element['filters'][2]['stepSize']
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
        finally:
            return False 
        
    


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
    
    
    

    def place_market_order(self, pair: str, side: str, quantity: float):
        """
        Размещает рыночный ордер
        :param pair: Торговая пара (например, 'BTCUSDT')
        :param side: Направление сделки ('BUY' или 'SELL')
        :param quantity: Количество для торговли
        :return: Информация об ордере или False в случае ошибки
        """
        try:
            response = self.f_client.new_order(
                symbol=pair,
                side=side,
                type='MARKET',
                quantity=quantity
            )
            print(f"Рыночный ордер размещен: {response}")
            return response
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            return False

    def place_limit_order(self, pair: str, side: str, quantity: float, price: float):
        """
        Размещает лимитный ордер
        :param pair: Торговая пара
        :param side: Направление сделки ('BUY' или 'SELL')
        :param quantity: Количество для торговли
        :param price: Цена ордера
        :return: Информация об ордере или False в случае ошибки
        """
        try:
            response = self.f_client.new_order(
                symbol=pair,
                side=side,
                type='LIMIT',
                timeInForce='GTC',
                quantity=quantity,
                price=price
            )
            print(f"Лимитный ордер размещен: {response}")
            return response
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            return False

    def place_stop_loss(self, pair: str, side: str, quantity: float, stop_price: float, close_position: bool = False):
        """
        Размещает стоп-лосс ордер
        :param pair: Торговая пара
        :param side: Направление сделки ('BUY' или 'SELL')
        :param quantity: Количество для торговли
        :param stop_price: Цена активации стоп-лосса
        :param close_position: Закрыть всю позицию (True) или частично (False)
        :return: Информация об ордере или False в случае ошибки
        """
        try:
            params = {
                'symbol': pair,
                'side': side,
                'type': 'STOP_MARKET',
                'stopPrice': stop_price,
                'closePosition': close_position
            }
            if not close_position:
                params['quantity'] = quantity

            response = self.f_client.new_order(**params)
            print(f"Стоп-лосс ордер размещен: {response}")
            return response
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            return False

    def place_trailing_stop(self, pair: str, side: str, quantity: float, callback_rate: float, activation_price: float = None):
        """
        Размещает трейлинг-стоп ордер
        :param pair: Торговая пара
        :param side: Направление сделки ('BUY' или 'SELL')
        :param quantity: Количество для торговли
        :param callback_rate: Процент отката для активации трейлинг-стопа
        :param activation_price: Цена активации трейлинг-стопа (опционально)
        :return: Информация об ордере или False в случае ошибки
        """
        try:
            params = {
                'symbol': pair,
                'side': side,
                'type': 'TRAILING_STOP_MARKET',
                'quantity': quantity,
                'callbackRate': callback_rate
            }
            if activation_price:
                params['activationPrice'] = activation_price

            response = self.f_client.new_order(**params)
            print(f"Трейлинг-стоп ордер размещен: {response}")
            return response
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            return False

    def cancel_all_orders(self, pair: str):
        """
        Отменяет все ордера для указанной пары
        :param pair: Торговая пара
        :return: True в случае успеха, False в случае ошибки
        """
        try:
            response = self.f_client.cancel_open_orders(symbol=pair)
            print(f"Все ордера отменены: {response}")
            return True
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            return False

    def get_position_info(self, pair: str):
        """
        Получает информацию о позиции
        :param pair: Торговая пара
        :return: Информация о позиции или False в случае ошибки
        """
        try:
            response = self.f_client.get_position_risk(symbol=pair)
            print(f"Информация о позиции: {response}")
            return response
        except ClientError as error:
            print(
                "Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            return False
    
    
    
