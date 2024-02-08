import pandas as pd
import ta.momentum as tam


def RSI(ohlvc) -> int:
    
    rsi_period = 14
    
    ohlvc['Close'] = pd.to_numeric(ohlvc['Close'])      #convert the value to numeric type, so it can be calculated
    ohlvc.drop(ohlvc.index[-1], inplace=True)       #drop the last constantly changing candle close value
    
    rsi = tam.RSIIndicator(ohlvc['Close'], window=rsi_period).rsi().iloc[-1]
        
    return int(round(rsi, 0))