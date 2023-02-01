import pprint
from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass
class Resistance():
    time: datetime
    low: float
    high: float
    broken: bool = False
    timeframe: str = ''
    
    def __repr__(self):
        return f"Resistance {self.time} - l: {self.low}, h: {self.high}, {self.timeframe}, {'not ' if not self.broken else ''}broken"

@dataclass
class Support():
    time: datetime
    low: float
    high: float
    broken: bool = False
    timeframe: str = ''
    
    def __repr__(self):
        return f"Support    {self.time} - l: {self.low}, h: {self.high}, {self.timeframe}, {'not ' if not self.broken else ''}broken"
    
def find_levels(candles: pd.DataFrame, timeframe: str) -> list:
    shift = 0
    pattern_type = ['Support', 'Resistance', '--']
    supports = []
    resistances = []
    levels = []     # supports and resistances combined in one list
        
    for _ in range(0, candles.shape[0] - 4):    # Go through all candles in dataframe
        
        candle_pattern = []
       
        for i in range(0,5):
            if candles.at[shift + i, 'Open'] > candles.at[shift + i, 'Close']:  # Down (red) candle
                candle_pattern.append(0)
            elif candles.at[shift + i, 'Open'] < candles.at[shift + i, 'Close']:    # Up (green) candle
                candle_pattern.append(1)
            else:
                print('Holy shit, Open and Close are exactly the same value!')

        
        # checking for supports
        if analyze_pattern(candle_pattern) == 0:
            
            lows = [] # list of low prices in pattern
            bodies = [] # list of open and close prices in pattern   
            
            for i in range(0,5):
                lows.append(candles.at[shift + i, 'Low'])
                bodies.append(candles.at[shift + i, 'Open'])
                bodies.append(candles.at[shift + i, 'Close'])
                
                
            # finding the indicative candle for lever (min low in pattern)
            level_time_shift = lows.index(min(lows))    
            
            support_time = datetime.fromtimestamp(int(candles.at[shift + level_time_shift, 'O_time'])/1000)
            
            if Support(time=support_time, low=min(lows), high=min(bodies)) not in supports:
                supports.append(Support(time=support_time, low=min(lows), high=min(bodies), timeframe=timeframe))
                levels.append(Support(time=support_time, low=min(lows), high=min(bodies), timeframe=timeframe))
        
        # checking for resistances 
        if analyze_pattern(candle_pattern) == 1:
            
            highs = [] # list of low prices in pattern
            bodies = [] # list of open and close prices in pattern   
            
            for i in range(0,5):
                highs.append(candles.at[shift + i, 'High'])
                bodies.append(candles.at[shift + i, 'Open'])
                bodies.append(candles.at[shift + i, 'Close'])
            
            # finding the indicative candle for lever (max high in pattern)
            level_time_shift = highs.index(max(highs))
            
            resistance_time = datetime.fromtimestamp(int(candles.at[shift + level_time_shift, 'O_time'])/1000)
            
            if Resistance(time=resistance_time, low=max(bodies), high=max(highs)) not in resistances:
                resistances.append(Resistance(time=resistance_time, low=max(bodies), high=max(highs), timeframe=timeframe))
                levels.append(Resistance(time=resistance_time, low=max(bodies), high=max(highs), timeframe=timeframe))
                
                
        #print(int(candles.at[shift + i, 'O_time']/10000))
        
        # time = datetime.fromtimestamp(int(candles.at[shift, 'O_time'])/1000)    # timestamp from Binannce is in microseconds
        # print(time , ' ', level, ' ',  candle_pattern)            
        shift += 1
    
    
    check_level_breaks(levels)
    
    for level in levels:
        print(level) 
    # for support in supports:
    #     print(f'Support time: {support.time}, low: {support.low}, high: {support.high}')
    # for resistance in resistances:
    #     print(f'Resistance time: {resistance.time}, low: {resistance.low}, high: {resistance.high}')
        
    return levels
                    


def analyze_pattern(pattern: list):
    
    if pattern == [1, 1, 0, 0, 0] or pattern == [1, 1, 0, 0, 1]:
        # print('↑↑↓↓-')
        return 1 # resistance
    elif pattern == [1, 1, 1, 0, 0] or pattern == [0, 1, 1, 0, 0]:
        # print('-↑↑↓↓')
        return 1 # resistance
    elif pattern == [1, 0, 1, 0, 0]:   # ↑↓↑↓↓
        # print('↑↓↑↓↓')
        return 1 # resistance
    elif pattern == [1, 1, 0, 1, 0]:   # ↑↑↓↑↓
        # print('↑↑↓↑↓')
        return 1 # resistance
    elif pattern == [0, 0, 1, 1, 0] or pattern == [0, 0, 1, 1, 1]:   # ↓↓↑↑-
        # print('↓↓↑↑-')
        return 0 # support
    elif pattern == [0, 0, 0, 1, 1] or pattern == [1, 0, 0, 1, 1]:   # -↓↓↑↑
        # print('-↓↓↑↑')
        return 0 # support
    elif pattern == [0, 1, 0, 1, 1]:   # ↓↑↓↑↑
        # print('↓↑↓↑↑')
        return 0 # support
    elif pattern == [0, 0, 1, 0, 1]:   # ↓↓↑↓↑
        # print('↓↓↑↓↑')
        return 0 # support
    else: 
        return 2
        
        
def check_level_breaks(levels: list) -> list:

    for i in range(0, len(levels) - 1):
        shift = i + 1
        print(f'levels len = {len(levels)}')
        print(f'i={i}, k={shift}')
        
        if levels[i].__class__ is Resistance:
            for k in range(shift, len(levels) - 1):
                if levels[k].__class__ is Resistance and levels[k].low > levels[i].high:
                     levels[i].broken = True
                     break
        elif levels[i].__class__ is Support:
            for k in range(shift, len(levels) - 1):
                if levels[k].__class__ is Support and levels[k].high < levels[i].low:
                    levels[i].broken = True
                    break
        else:
            print('Wrong level type(class)!')    
            
    return levels