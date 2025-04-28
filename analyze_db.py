import sqlite3
import pandas as pd
from datetime import datetime

def analyze_database(db_path):
    print(f"\nАнализ базы данных: {db_path}")
    
    # Подключаемся к базе данных
    conn = sqlite3.connect(db_path)
    
    # Получаем список всех таблиц
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("\nТаблицы в базе данных:")
    for table in tables:
        table_name = table[0]
        print(f"\nТаблица: {table_name}")
        
        # Получаем структуру таблицы
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        print("Структура таблицы:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Получаем количество записей
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"Количество записей: {count}")
        
        # Получаем примеры данных
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        rows = cursor.fetchall()
        print("\nПримеры записей:")
        for row in rows:
            print(row)
    
    # Анализ сделок
    if 'deals' in [t[0] for t in tables]:
        # Общая статистика
        df = pd.read_sql_query("""
            SELECT 
                COUNT(*) as total_deals,
                SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) as profitable_deals,
                SUM(CASE WHEN status = 'loss' THEN 1 ELSE 0 END) as losing_deals,
                AVG(profit_loss) as avg_profit_loss,
                SUM(profit_loss) as total_profit_loss,
                MIN(profit_loss) as min_profit_loss,
                MAX(profit_loss) as max_profit_loss
            FROM deals
        """, conn)
        
        print("\nОбщая статистика по сделкам:")
        print(df)
        
        # Статистика по парам
        df_pairs = pd.read_sql_query("""
            SELECT 
                pair,
                COUNT(*) as total_deals,
                SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) as profitable_deals,
                SUM(CASE WHEN status = 'loss' THEN 1 ELSE 0 END) as losing_deals,
                AVG(profit_loss) as avg_profit_loss,
                SUM(profit_loss) as total_profit_loss
            FROM deals
            GROUP BY pair
            ORDER BY total_deals DESC
        """, conn)
        
        print("\nСтатистика по торговым парам:")
        print(df_pairs)
        
        # Статистика по времени
        df_time = pd.read_sql_query("""
            SELECT 
                strftime('%Y-%m-%d', datetime) as date,
                COUNT(*) as total_deals,
                SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) as profitable_deals,
                SUM(CASE WHEN status = 'loss' THEN 1 ELSE 0 END) as losing_deals,
                AVG(profit_loss) as avg_profit_loss,
                SUM(profit_loss) as total_profit_loss
            FROM deals
            GROUP BY date
            ORDER BY date
        """, conn)
        
        print("\nСтатистика по дням:")
        print(df_time)
    
    conn.close()

# Анализируем базу данных
analyze_database('deals_5m.sqlite') 