## BRIEF DESCRIPTION

This bot gives signals in telegram bot when the situation on the crypto-market meets some determined conditions.   
It may give the trader opportunity not to monitor market situation all the time

## FUNCTIONS

Bot checks the list of pre-determined trading pairs after each candle closes on the chosen timeframe (different timeframes?)
If the market situation meets needed conditions bot sends message to telegram user with parameters of offered deal

## TODO

- [X] function detecting levels of supports and resistances on one pair and on the determined timeframe
- [X] function checking if the level is already broken by existing candles and adding this info to level instance
- [X] function that receives market data from Binance (pair, timeframe, candle quantity) and returning Pandas dataframe of OHLVC data
- [X] fucntion assigning density property to levels
- [X] function running candle check after the next candle closes
- [X] function checking closed candle to break through support or resistance level
- [X] function finding distance to stop loss based on stop loss determining mode
- [X] function finding distance to take profit based on take profit determining mode  
- [X] function checking the possibility to make deal based on market situation and money and risk management
- [X] function offering deal parameters (amount, stop-loss and take levels, leverage etc.) if the market situation meets conditions
    - [X] add to config file desired parameters for deal making
- [X] function running checks through determined trading pair list
- [X] function writing deal with its parameters to database
- [X] function checking each deal for win or loss after every candle closes
    - [X] get the list of active deals
    - [X] check win
    - [X] check loss
    - [X] write best and worst price if deal haven't won or lost
    - [Х] changing status of a deal depending on result
    - [X] check only active deal (separate function)
- [ ] bot run with parameters in comand line
- [ ] function for statistics display

- [ ] strategy setup to separate file so strategy could be defined through config(?)

## IDEAS

- [X] Different candle depth for different timeframes?
- Store previous candle data and update only new candles or request all candle data each time?
- Check level for each timeframe only after new candle closes?
- Historical backtesting 
- Optimization of deal parameters on historical data
