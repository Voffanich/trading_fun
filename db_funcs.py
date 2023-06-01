import copy
import os
import shutil
import sqlite3
from datetime import datetime as dt
from datetime import timedelta
from typing import Dict, List
from xmlrpc.client import Boolean

import pandas as pd
import portion as p


class DB_handler():
    
    def __init__(self, dbname='deals.sqlite'):
        self.dbname = dbname
        self.connection = sqlite3.connect(dbname, check_same_thread=False)
        self.cursor = self.connection.cursor()
        self.flag = ''
        
    def setup(self):
        query = """CREATE TABLE IF NOT EXISTS deals (
            deal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL,
            pair TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            direction TEXT NOT NULL,
            profit_loss REAL NOT NULL,
            entry_price REAL NOT NULL,
            take_price REAL NOT NULL,
            stop_price REAL NOT NULL,
            take_dist_perc REAL NOT NULL,
            stop_dist_perc REAL NOT NULL,
            best_price REAL,
            worst_price REAL,
            result TEXT,
            status TEXT,
            indicators TEXT);
            """
        try:    
            self.cursor.execute(query)
            self.connection.commit()
        except sqlite3.Error as error:
            print('SQLite error: ', error)
            return error
        
    def add_deal(self, deal):
        query = """
        INSERT INTO deals (datetime, pair, timeframe, direction, profit_loss, entry_price, take_price, stop_price, take_dist_perc, 
        stop_dist_perc, status, indicators)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?); 
        """
        try:
            self.cursor.execute(query, (dt.strftime(dt.now(), '%Y-%m-%d %H:%M:%S'), deal.pair, deal.timeframe, deal.direction, deal.profit_loss_ratio, deal.entry_price, 
                                        deal.take_price, deal.stop_price, deal.take_distance_percentage, deal.stop_distance_percentage, 'active', ''))
            self.connection.commit()
        except sqlite3.Error as error:
            print('SQLite error: ', error)
            return error
            
        

db = DB_handler()