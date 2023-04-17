import pprint
from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass
class Resistance():
    time: datetime
    low: float
    high: float
    timeframe: str
    broken: bool = None
    density: float = None 
    
    def __repr__(self):
        return "Resistance {} - l: {:<10} h: {:<10} {}, {:<10}, {}".format(self.time, self.low, self.high, self.timeframe, 
                                                                           'not broken' if not self.broken else 'broken', self.density)

@dataclass
class Support():
    time: datetime
    low: float
    high: float
    timeframe: str
    broken: bool = None
    density: float = None   
    
    def __repr__(self):
        return f"Support    {self.time} - l: {self.low:<10} h: {self.high:<10} {self.timeframe}, {'not broken' if not self.broken else 'broken':<10}, {self.density}"
        # return f"Support    {self.time} - l: {self.low:9d}, h: {self.high:9d}, {self.timeframe}, {'not ' if not self.broken else ''}broken"
        
@dataclass
class Level():
    time: datetime
    low: float
    high: float
    timeframe: str
    broken: bool = None
    density: float = None   
    
    def __repr__(self):
        return f"Level      {self.time} - l: {self.low:<10} h: {self.high:<10} {self.timeframe}, {'not broken' if not self.broken else 'broken':<10}, {self.density}"
        # return f"Support    {self.time} - l: {self.low:9d}, h: {self.high:9d}, {self.timeframe}, {'not ' if not self.broken else ''}broken"
        
@dataclass
class Deal():
    
    pass

    
def find_levels(candles: pd.DataFrame, timeframe: str) -> list:
    shift = 0
    pattern_type = ['Support', 'Resistance', '--']
    supports = []
    resistances = []
    levels = []     # supports and resistances combined in one list
    prelast_candle_close = float(candles.at[candles.shape[0] - 3, 'Close'])  # close price of the PRE-last closed candle to see the break of the last levels
    
        
    for _ in range(0, candles.shape[0] - 4):    # Go through all candles in dataframe
        
        candle_pattern = []
       
        for i in range(0,5):
            if candles.at[shift + i, 'Open'] > candles.at[shift + i, 'Close']:  # Down (red) candle
                candle_pattern.append(0)
            elif candles.at[shift + i, 'Open'] <= candles.at[shift + i, 'Close']:    # Up (green) candle
                candle_pattern.append(1)
            else:
                print('Holy shit, something went wrong in candle direction checking!')

        
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
            
            if Support(time=support_time, low=float(min(lows)), high=float(min(bodies)), timeframe=timeframe) not in supports:
                supports.append(Support(time=support_time, low=float(min(lows)), high=float(min(bodies)), timeframe=timeframe))
                levels.append(Support(time=support_time, low=float(min(lows)), high=float(min(bodies)), timeframe=timeframe))
        
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
            
            if Resistance(time=resistance_time, low=float(max(bodies)), high=float(max(highs)), timeframe=timeframe) not in resistances:
                resistances.append(Resistance(time=resistance_time, low=float(max(bodies)), high=float(max(highs)), timeframe=timeframe))
                levels.append(Resistance(time=resistance_time, low=float(max(bodies)), high=float(max(highs)), timeframe=timeframe))
                
                
        #print(int(candles.at[shift + i, 'O_time']/10000))
        
        # time = datetime.fromtimestamp(int(candles.at[shift, 'O_time'])/1000)    # timestamp from Binannce is in microseconds
        # print(time , ' ', level, ' ',  candle_pattern)            
        shift += 1
    
    
    levels = check_level_breaks(levels, prelast_candle_close)
    
    # for level in levels:
    #     print(level) 
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
        
        
def check_level_breaks(levels: list, prelast_candle_close: float) -> list:
    
    for i in range(0, len(levels)):
        shift = i + 1       # shift for first index for later levels check
                
        if levels[i].__class__ is Resistance:
            for k in range(shift, len(levels)):
                if levels[k].__class__ is Resistance and (levels[k].low > levels[i].high or prelast_candle_close > levels[i].high):
                     levels[i].broken = True
                     break
        elif levels[i].__class__ is Support:
            for k in range(shift, len(levels)):
                if levels[k].__class__ is Support and (levels[k].high < levels[i].low or prelast_candle_close < levels[i].low):
                    levels[i].broken = True
                    break
        else:
            print('Wrong level type(class)!')    
            
    return levels

# CHECK THE ALGO FOR USE OF WHILE INSTEAD OF FOR 
def merge_all_levels(levels: list) -> list:
    # for level in levels:
    #     for level2 in levels:
    #         if ((level.low <= level2.high and level.low >= level2.low) or (level.high <= level2.high and level.high >= level2.low)) and level != level2:
    #             new_level = Level(min(level.time, level2.time), min(level.low, level2.low), max(level.high, level2.high), 
    #                                    level.timeframe, level.broken or level2.broken, level.density + level2.density)
    #             # levels.remove(level)
    #             # levels.remove(level2)
    #             levels.append(new_level)
    #             print('New level ', new_level)
    #         else:
    #             print('No intersections')
    
    while True:  
        intersections = 0          
        for index, level in enumerate(levels):
            for index2, level2 in enumerate(levels):
                if index2 > index:
                    if ((level.low <= level2.high and level.low >= level2.low) or (level.high <= level2.high and level.high >= level2.low)) and level != level2:
                        new_level = Level(min(level.time, level2.time), min(level.low, level2.low), max(level.high, level2.high), 
                                        higher_timeframe(level.timeframe, level2.timeframe), level.broken or level2.broken, level.density + level2.density)
                        # print(f'New level: {new_level}')
                        # print(f'len(levels) = {len(levels)}')
                        # print(f'index = {index}')
                        # print(f'index2 = {index2}')
                        del levels[index2]
                        del levels[index]
                        levels.append(new_level)
                        intersections += 1
                    # else:
                    #     new_level = Level(level.time, level.low, level.high, level.timeframe, level.broken, level.density)
                    #     del levels[index]
                    #     levels.append(new_level)
        if intersections == 0:
            break
    return levels

def merge_timeframe_levels(levels: list, console_log: bool = False) -> list:
    while True: 
        intercections = 0
        for index, level in enumerate(levels):
            for index2, level2 in enumerate(levels):
                if index2 > index:
                    if level.timeframe == level2.timeframe and level.__class__ == level2.__class__:
                        if ((level.low <= level2.high and level.low >= level2.low) or (level.high <= level2.high and level.high >= level2.low)) and level != level2:
                            merged_level = level.__class__(max(level.time, level2.time), min(level.low, level2.low), max(level.high, level2.high), 
                                        level.timeframe, level.broken and level2.broken, level.density + level2.density)
                            if console_log:
                                print(f'\nFound two levels with intersection')
                                print(f'level=        {level}')
                                print(f'level2=       {level2}')
                                print(f'merged level= {merged_level}')
                            levels.append(merged_level)
                            del levels[index2]
                            del levels[index] 
                            intercections += 1   
        if intercections == 0:
            break
    return levels

def higher_timeframe(timeframe1, timeframe2):
    timeframes = ["1m", "5m", "1h", "4h", "1d", "1w", "1M"]
    if timeframes.index(timeframe1) >= timeframes.index(timeframe2):
        return timeframe1
    else:
        return timeframe2

def assign_level_density(levels: list, checked_timeframes: list, levels_config: dict) -> list:
    density_coefficient = 1
    broken_density_factor = levels_config['broken_density_factor']
    upper_level_density_factor = levels_config['upper_level_density_factor']
    
    for timeframe in checked_timeframes:
        for level in levels:
            if level.broken and level.timeframe == timeframe:
                level.density = density_coefficient * broken_density_factor
            if not level.broken and level.timeframe == timeframe:
                level.density = density_coefficient
        
        density_coefficient *= upper_level_density_factor
    
    # for level in levels:
    #     print(level)
    # print('______________')
    
    # levels = merge_all_levels(levels)
        
    return levels

# just delete broken levels of basic timeframe
def optimize_levels(levels: list, checked_timeframes: list) -> list:
    basic_timeframe = True
    for timeframe in checked_timeframes:
        
        index = 0
        while index < len(levels):
            if levels[index].timeframe == timeframe and basic_timeframe:
                
                if levels[index].broken:
                    del levels[index]
                else:
                    index += 1    
            else:
                break                   
                    
        basic_timeframe = False    
       
    return levels

def filter_basic_timeframe_levels(level):
    pass
    

def check_deal(levels: list, last_candle: object, deal_config: dict, trading_timeframe: str) -> Deal:
    basic_timeframe_levels = list(filter(lambda level: level.timeframe == trading_timeframe, levels))
    
    print(f'deal_config = {deal_config}')
    
    for level in basic_timeframe_levels: 
        if float(last_candle.Open) > level.low and float(last_candle.Close) < level.low and level.__class__ is Support:
            print(f'Last candle: O {last_candle.Open}, С {last_candle.Close}')
            print(f'Level {level} broken down')
            
            stop_price(levels, last_candle, deal_config, level.__class__)
            take_price(levels, last_candle, deal_config)
            
        elif float(last_candle.Open) < level.high and float(last_candle.Close) > level.high  and level.__class__ is Resistance:
            print(f'Last candle: O {last_candle.Open}, С {last_candle.Close}')
            print(f'Level {level} broken up')
        

def stop_price(levels: list, last_candle: object, deal_config: dict, broken_level_type: str) -> list:
    
    pass


def take_price() -> list:
    pass


    
def print_levels(levels: list):
    for level in levels:
        print(level)