import copy
import os
import re
import shutil
import sqlite3
from datetime import datetime as dt
from datetime import timedelta
from typing import Dict, List
from xmlrpc.client import Boolean

import pandas as pd
import portion as p

import aux_funcs as af
import levels as lv


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
        stop_dist_perc, best_price, worst_price, status, indicators)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?); 
        """
        try:
            self.cursor.execute(query, (dt.strftime(dt.now(), '%Y-%m-%d %H:%M:%S'), deal.pair, deal.timeframe, deal.direction, 
                                        deal.profit_loss_ratio, af.r_signif(deal.entry_price, 4), 
                                        af.r_signif(deal.take_price, 4), af.r_signif(deal.stop_price, 4), deal.take_dist_perc, 
                                        deal.stop_dist_perc, deal.best_price, deal.worst_price, deal.status, deal.indicators))
            self.connection.commit()
        except sqlite3.Error as error:
            print('SQLite error: ', error)
            return error
            
    def read_active_deals(self, pair: str) -> list[object]:
        query = """
        SELECT * FROM deals
        WHERE status = 'active' AND pair = ?;
        """
        try:    
            self.cursor.execute(query, (pair,))
            deals = self.cursor.fetchall()
            self.connection.commit()
            
            # print(deals[:10])
            
            deals_list = []
            
            for deal in deals:
                deals_list.append(lv.Deal(
                    deal_id=deal[0],
                    timestamp=deal[1],
                    pair=deal[2],
                    timeframe=deal[3],
                    direction=deal[4],
                    profit_loss_ratio=deal[5],
                    entry_price=deal[6],
                    take_price=deal[7],
                    stop_price=deal[8],
                    take_dist_perc=deal[9],
                    stop_dist_perc=deal[10],
                    best_price=deal[11],
                    worst_price=deal[12],
                    best_price_perc=deal[13],
                    worst_price_perc=deal[14],
                    current_price=deal[15],                   
                    current_price_perc=deal[16],                   
                    status=deal[17],
                    finish_time=deal[18],
                    indicators=deal[19],
                    leverage=10                                        
                ))
            
            return deals_list
        
        except sqlite3.Error as error:
            print('SQLite error: ', error)
            return error
    
    def update_deal_data(self, column: str, value, deal_id: int):
        if re.fullmatch(r'[a-zA-Z0-9_]*', column):
            query = f"""
            UPDATE deals
            SET {column}=?
            WHERE deal_id=?;
            """    
            try:    
                self.cursor.execute(query, (value, deal_id))
                self.connection.commit()
            except sqlite3.Error as error:
                print('SQLite error: ', error)
                return error   
        else:
            return 'Don\'t you dare sending me anything except latin letters, figures and underscores!'

    def get_active_deals_list(self) -> list:
        query = """
        SELECT pair FROM deals
        WHERE status = 'active'
        GROUP BY pair;
        """
        try:    
            self.cursor.execute(query)
            active_deal_pairs = self.cursor.fetchall()
            self.connection.commit()    
            
            active_deals_pair_list = [pair[0] for pair in active_deal_pairs]
                        
            return active_deals_pair_list
                
        except sqlite3.Error as error:
            print('SQLite error: ', error)
            return error
        
        
db = DB_handler()