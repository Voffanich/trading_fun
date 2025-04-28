import sqlite3
import pandas as pd

def check_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Получаем список таблиц
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Таблицы в базе данных:")
    for table in tables:
        print(f"\nТаблица: {table[0]}")
        
        # Получаем структуру таблицы
        cursor.execute(f"PRAGMA table_info({table[0]});")
        columns = cursor.fetchall()
        print("Колонки:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Получаем первые 5 записей
        cursor.execute(f"SELECT * FROM {table[0]} ORDER BY datetime LIMIT 5;")
        rows = cursor.fetchall()
        print("\nПервые 5 записей:")
        for row in rows:
            print(row)
            
        # Получаем последние 5 записей
        cursor.execute(f"SELECT * FROM {table[0]} ORDER BY datetime DESC LIMIT 5;")
        rows = cursor.fetchall()
        print("\nПоследние 5 записей:")
        for row in rows:
            print(row)
            
        # Получаем диапазон дат
        cursor.execute(f"SELECT MIN(datetime), MAX(datetime) FROM {table[0]};")
        min_date, max_date = cursor.fetchone()
        print(f"\nДиапазон дат: с {min_date} по {max_date}")
    
    conn.close()

if __name__ == "__main__":
    check_database("../deals_1h.sqlite") 