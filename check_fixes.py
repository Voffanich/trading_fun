#!/usr/bin/env python3
"""
Скрипт для проверки применения исправлений Order Manager
"""

import os
import sys

def check_file_contains(file_path, search_strings):
    """Проверяет, содержит ли файл указанные строки"""
    if not os.path.exists(file_path):
        return False, f"Файл {file_path} не найден"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        missing = []
        for search_str in search_strings:
            if search_str not in content:
                missing.append(search_str)
        
        if missing:
            return False, f"Отсутствуют строки: {missing}"
        return True, "Все проверки пройдены"
    
    except Exception as e:
        return False, f"Ошибка чтения файла: {e}"

def main():
    print("🔍 Проверка применения исправлений Order Manager...")
    print("=" * 60)
    
    # Проверки для order_manager.py
    print("📁 Проверка order_manager.py:")
    order_manager_checks = [
        "entry_orders = [o for o in open_orders if (o.get(\"type\") == \"LIMIT\" and o.get(\"orderId\"))]",
        "prot_orders = [o for o in open_orders if (o.get(\"type\") in (\"STOP_MARKET\", \"TRAILING_STOP_MARKET\") and o.get(\"orderId\"))]",
        "cleanup_debug",
        "watch_and_cleanup_error"
    ]
    
    success, message = check_file_contains("order_manager.py", order_manager_checks)
    print(f"   {'✅' if success else '❌'} {message}")
    
    # Проверки для binance_connect.py
    print("\n📁 Проверка binance_connect.py:")
    binance_checks = [
        "if order_id is not None and order_id != 0:",
        "cancel_order skipped"
    ]
    
    success, message = check_file_contains("binance_connect.py", binance_checks)
    print(f"   {'✅' if success else '❌'} {message}")
    
    # Проверки для bot_5m_rm.py
    print("\n📁 Проверка bot_5m_rm.py:")
    bot_checks = [
        "OrderManager cleanup: processing",
        "verbose=True"
    ]
    
    success, message = check_file_contains("bot_5m_rm.py", bot_checks)
    print(f"   {'✅' if success else '❌'} {message}")
    
    # Проверка индикаторного файла
    print("\n📁 Проверка индикаторного файла:")
    if os.path.exists("ORDER_MANAGER_FIXES_APPLIED.md"):
        print("   ✅ ORDER_MANAGER_FIXES_APPLIED.md найден")
    else:
        print("   ❌ ORDER_MANAGER_FIXES_APPLIED.md не найден")
    
    print("\n" + "=" * 60)
    print("🎯 Проверка завершена!")
    print("\nЕсли все проверки пройдены ✅, то исправления применены корректно.")
    print("Можете перезапускать бота!")

if __name__ == "__main__":
    main()