## BRIEF DESCRIPTION

This bot gives signals in telegram bot when the situation on the crypto-market meets some determined conditions.   
It may give the trader opportunity not to monitor market situation all the time

## FUNCTIONS

Bot checks the list of pre-determined trading pairs after each candle closes on the chosen timeframe (different timeframes?)
If the market situation meets needed conditions bot sends message to telegram user with parameters of offered deal

## TODO

- [X] function detecting levels of supports and resistances on one pair and on the determined timeframe
- [X] function checking if the level is already broken by existing candles and adding this info to level instance
- [X] functions that receives market data from Binance (pair, timeframe, candle quantity) and returning Pandas dataframe of OHLVC data
- [ ] function running candle check after the next candle closes
- [ ] function checking closed candle to break through support or resistance level
- [ ] function checking the possibility to make deal based on market situation and money and risk management
- [ ] function offering deal parameters (amount, stop-loss and take levels, leverage etc.) if the market situation meets conditions
    - [ ] add to config file desired parameters for deal making
- [ ] function running checks through determined trading pair list

## IDEAS

- Different candle depth for different timeframes?
- Historical backtesting 
- Optimization of deal parameters on historical data
