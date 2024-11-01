from binance.spot import Spot

from user_data.credentials import bnc_api_key, bnc_api_secret

client = Spot()

# Get server timestamp
# print(client.time())
# Get klines of BTCUSDT at 1m interval
# print(client.klines("BTCUSDT", "1m"))
# # Get last 10 klines of BNBUSDT at 1h interval
# print(client.klines("BNBUSDT", "1h", limit=10))

# API key/secret are required for user data endpoints
client = Spot(api_key=bnc_api_key, api_secret=bnc_api_secret)

# response = client.new_order('ADAUSDT', 'BUY', 'LIMIT', timeInForce='GTC', quantity=60, price=0.1 )
response = client.new_order('ADAUSDT', 'BUY', 'LIMIT', timeInForce='GTC', quantity=60, price=0.1 )

print(response)
# Get account and balance information
# print(client.account())

# print(client.asset_detail())
# Post a new order
params = {
    'symbol': 'BTCUSDT',
    'side': 'SELL',
    'type': 'LIMIT',
    'timeInForce': 'GTC',
    'quantity': 0.002,
    'price': 9500
}
