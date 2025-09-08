## Feature Log

Этот файл фиксирует изменения функционала (методы, конфиги, фичи). Все новые возможности должны документироваться здесь.

### 2025-09-05

- Добавлен модуль `order_manager.py` (оркестратор ордеров/позиций Binance):
  - Асинхронное размещение входа и защит (LIMIT + STOP_MARKET + TRAILING_STOP_MARKET) с ретраями и откатом.
  - Проверки факта размещения, догон защитных ордеров, отмена «лишнего».
  - Отмена оставшегося ордера при срабатывании стопа/трейлинга.
  - Ограничение проскальзывания по `markPrice` (config).
  - Логирование в консоль и файл `logs/order_manager.log` (JSON-формат).
- Расширен `Binance_connect`:
  - Методы: `get_open_orders(symbol)`, `get_order(symbol, orderId|origClientOrderId)`, `cancel_order(...)`, `cancel_all_open_orders(symbol)`, `get_position(symbol)`, `get_mark_price(symbol)`.
  - Строгое форматирование чисел по `tickSize/stepSize` (Decimal) для избежания ошибок точности (-1111).
  - Полная поддержка Portfolio Margin (PAPI) для UM: размещение/отмена ордеров (`/papi/v1/um/order`, `/papi/v1/um/allOpenOrders`), чтение `openOrders`, `premiumIndex`, `account`, смена плеча и типа маржи (`/papi/v1/um/leverage`, `/papi/v1/um/marginType`). Переключение через `general.futures_api_mode: classic|pm`.
- Расширен `DB_handler`:
  - Таблица `exchange_orders` для хранения активных ордеров (mapping `deal_id ↔ clientOrderId/orderId`, тип, статус, цены, qty).
  - CRUD и восстановление состояния при старте.
- Конфиг (`config_5m_rm.json`):
  - `general.use_order_manager: true|false` — включение менеджера.
  - `order_manager`: `{ "retries": 3, "backoff_sec": [0.5,1,2], "poll_interval_sec": 2, "placement_timeout_sec": 15, "max_slippage_pct": 0.2, "unfilled_entry_ttl_sec": 0 }`.
- Интеграция в `bot_5m_rm.py`:
  - После формирования сделки — вызов `OrderManager.place_managed_trade(...)` вместо прямого размещения.
  - В минутном цикле — `OrderManager.watch_and_cleanup()`.

Примечание: менеджер опционален и может быть отключён флагом конфигурации.

