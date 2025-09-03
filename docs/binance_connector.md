# Binance Futures Connector — руководство по использованию

Этот документ описывает, как работает класс `Binance_connect` из файла `binance_connect.py`, как с его помощью размещать сделки, какие есть параметры (все опции), в каких единицах они указываются, а также логику работы и типичные сценарии.

Документ относится к фьючерсам USDT-M на Binance (UM Futures). Коннектор поддерживает работу как с основной средой, так и с тестовой (`testnet`).

## Содержание
- Введение и архитектура
- Установка и требования
- Инициализация клиента
- Единицы измерения и терминология
- Метаданные символа и округления
- Расчёт размера позиции (количества)
- Получение баланса USDT
- Настройка аккаунта (плечо, тип маржи)
- Размещение сделки с защитными ордерами
  - Полный перечень параметров
  - Логика пошагово
  - Какие ордера выставляются
- Валидации и ограничения биржи
- Ошибки и коды ошибок
- Практические примеры
- Примечания и лучшие практики

---

## Введение и архитектура

`Binance_connect` — это тонкая обёртка над официальным клиентом `binance.um_futures.UMFutures`, упрощающая:
- настройку плеча и типа маржи для конкретного символа;
- вычисление размера позиции в штуках контракта (quantity) от суммы в USDT либо от риска на сделку;
- корректное округление цен и количества по фильтрам биржи (tickSize, stepSize);
- размещение набора ордеров: вход лимитом (LIMIT), стоп-лосс (STOP_MARKET), опционально тейк-профит (TAKE_PROFIT_MARKET) и трейлинг-стоп (TRAILING_STOP_MARKET).

Класс возвращает унифицированный объект результата `OrderResult` с полями успеха/ошибки и сырыми ответами API.

---

## Установка и требования

- Требуется установленный пакет `python-binance` (см. `requirements.txt`).
- Необходимы API ключ и секрет субаккаунта/аккаунта Binance с доступом к UM Futures.
- Для работы с тестовой средой (testnet) должен быть включён флаг `testnet=True` при инициализации.

---

## Инициализация клиента

```python
from binance_connect import Binance_connect

conn = Binance_connect(
	api_key="<BINANCE_API_KEY>",
	api_secret="<BINANCE_API_SECRET>",
	testnet=True,             # True — тестовая среда, False — боевая
	recv_window_ms=60000      # recvWindow для запросов (мс)
)
```

- `testnet`: при True используется базовый URL `https://testnet.binancefuture.com`.
- `recv_window_ms`: глобально задаёт `recvWindow` для запросов.

---

## Единицы измерения и терминология

- **symbol**: строка, например `"ETHUSDT"`.
- **side**: `"BUY"` или `"SELL"`.
- **price**: цена в долларах США (USDT) для линейных фьючерсов.
- **quantity (qty)**: количество контракта в штуках (например, 0.01 ETH). Указывается как число с плавающей точкой, округляется по `stepSize`.
- **notional_usdt**: номинал позиции в USDT. Используется для вычисления `quantity` как `notional_usdt / entry_price`.
- **risk_percent_of_bank**: риск на сделку в процентах от капитала в USDT.
- **leverage**: кредитное плечо, целое число, задаётся на символ перед размещением ордеров.
- **margin_type**: `"ISOLATED"` (по умолчанию) или `"CROSSED"`.
- **working_type**: тип триггера для стоп-ордеров, `"MARK_PRICE"` (по умолчанию) или `"CONTRACT_PRICE"`.
- **time_in_force**: TIF для лимит-ордера входа, по умолчанию `"GTC"`.
- **position_side**: режим для Hedge Mode; по умолчанию `"BOTH"` для One-way.
- **trailing_callback_percent**: процент отката для трейлинг-стопа (допустимо у Binance 0.1% — 5%; коннектор автоматически зажимает в эти границы).

---

## Метаданные символа и округления

Коннектор получает `exchange_info()` и извлекает для символа:
- `tickSize` — шаг цены; цены округляются кратно этому шагу.
- `stepSize` — шаг количества; количество округляется кратно этому шагу.
- `minQty` — минимально допустимое количество.
- `minNotional`/`notional` — минимально допустимый номинал ордера (цена × количество).

Округление выполняется «вниз» до ближайшего шага биржи.

---

## Расчёт размера позиции (количества)

Доступны три подхода, если `quantity` не задан явно:

1) Из номинала в USDT:
```python
qty = notional_usdt / entry_price
```
Далее `qty` округляется по `stepSize`, проверяется на `minQty`.

2) Из риска на сделку (при заданных `bank_usdt` и `risk_percent_of_bank`):
```python
risk_amount = bank_usdt * (risk_percent_of_bank / 100)
per_unit_loss = abs(entry_price - stop_loss_price)
qty = risk_amount / per_unit_loss
```
Затем округление по `stepSize` и проверка на `minQty`.

3) Из риска с автоматическим чтением баланса:
Коннектор сам получает баланс USDT (wallet или available) и применяет формулу из п.2.

Если после округления количество меньше `minQty` или номинал меньше `minNotional`, будет выброшено исключение.

---

## Получение баланса USDT

```python
available = conn.get_usdt_balance(balance_type="available")
wallet = conn.get_usdt_balance(balance_type="wallet")  # по умолчанию
```

Возвращается число с плавающей точкой (USDT). В случае ошибки выбрасывается `RuntimeError` с сообщением Binance.

---

## Настройка аккаунта (плечо, тип маржи)

Перед размещением ордеров коннектор:
- Устанавливает тип маржи методом `change_margin_type` (`ISOLATED` по умолчанию). Если тип уже установлен, возможное сообщение об отсутствии необходимости смены типа игнорируется.
- Устанавливает кредитное плечо методом `change_leverage`.

Ошибки на этих шагах приводят к `RuntimeError`.

---

## Размещение сделки с защитными ордерами

Основной метод: `place_futures_order_with_protection(...)`

Обязательные параметры:
- `symbol: str` — например, `"ETHUSDT"`.
- `side: str` — `"BUY"` или `"SELL"`.
- `entry_price: float` — «референсная» цена входа из логики бота.
- `deviation_percent: float` — отклонение для лимит-ордера входа в процентах от `entry_price`:
  - BUY: лимит ставится НИЖЕ (`entry_price * (1 - dev/100)`)
  - SELL: лимит ставится ВЫШЕ (`entry_price * (1 + dev/100)`)
- `stop_loss_price: float` — цена срабатывания стоп-лосса.
- `trailing_activation_price: float` — цена активации трейлинг-стопа.
- `trailing_callback_percent: float` — процент отката трейлинг-стопа (зажимается в диапазон 0.1–5.0).
- `leverage: int` — плечо.

Варианты задания размера позиции (один из):
- `quantity: Optional[float]`
- `notional_usdt: Optional[float]`
- `risk_percent_of_bank: Optional[float]` (с `current_bank_usdt: Optional[float]` или без него — тогда баланс читается из API)

Дополнительные параметры:
- `take_profit_price: Optional[float]` — если задан, будет создан `TAKE_PROFIT_MARKET`.
- `margin_type: str = "ISOLATED"`
- `reduce_only: bool = True` — защитные ордера создаются с `reduceOnly=True`.
- `working_type: str = "MARK_PRICE"` — тип триггера стоп-ордеров.
- `time_in_force: str = "GTC"` — TIF для входа.
- `position_side: str = "BOTH"` — для One-way режима. В Hedge Mode указывайте нужную сторону.
- `verbose: bool = False` — подробный лог в stdout.

Возвращаемое значение: `OrderResult` с полями:
- `success: bool`
- `message: str`
- `error_code: Optional[int]`
- `entry_order`, `stop_order`, `take_profit_order`, `trailing_stop_order` — словари сырых ответов API по каждому ордеру (или `None`)
- `raw: Dict[str, Any]` — все сырые ответы, собранные по ключам.

### Логика пошагово
1) Логирует входные параметры (если `verbose=True`).
2) Загружает фильтры символа (`tickSize`, `stepSize`, `minQty`, `minNotional`).
3) Настраивает аккаунт: `margin_type` и `leverage`.
4) Определяет `quantity`, если не задано:
   - из `notional_usdt`;
   - из `risk_percent_of_bank` + `current_bank_usdt`;
   - из `risk_percent_of_bank` + авто-чтение баланса.
5) Вычисляет цену лимит-входа с отклонением, округляет цену и количество.
6) Валидирует `minQty` и `minNotional`.
7) Создаёт входной `LIMIT` ордер.
8) Создаёт `STOP_MARKET` (reduce-only) с `stopPrice`.
9) При наличии — создаёт `TAKE_PROFIT_MARKET` (reduce-only) с `stopPrice`.
10) Создаёт `TRAILING_STOP_MARKET` с `activationPrice` и `callbackRate`.
11) Возвращает `OrderResult` с деталями.

### Какие ордера выставляются
- Вход: `LIMIT` (по `time_in_force`, `positionSide`)
- Стоп-лосс: `STOP_MARKET` (`reduceOnly=True`, `workingType`)
- Тейк-профит: `TAKE_PROFIT_MARKET` (опционально, `reduceOnly=True`, `workingType`)
- Трейлинг-стоп: `TRAILING_STOP_MARKET` (`activationPrice`, `callbackRate`, `reduceOnly=True`)

Примечание: для стоп-ордеров и тейк-профита используется поле `quantity` (а не `closePosition=True`), чтобы явно контролировать объём и избегать конфликтов в Hedge Mode.

---

## Валидации и ограничения биржи

Перед созданием ордеров выполняется проверка:
- `quantity >= minQty`
- `price * quantity >= minNotional` (если биржа требует)

Округления цен и количества выполняются до кратности `tickSize` и `stepSize`. Если после округления ограничения нарушены, выбрасывается исключение с объяснением.

`trailing_callback_percent` зажимается в пределах 0.1–5.0, т.к. иначе бинанс вернёт ошибку валидации.

---

## Ошибки и коды ошибок

- Любая ошибка Binance SDK (`ClientError`) перехватывается, из неё извлекаются `error_code`/`status_code` и `error_message`.
- В результате метод возвращает `OrderResult(success=False, message=..., error_code=...)`.
- На критических шагах (баланс, плечо, тип маржи) возможны `RuntimeError` с сообщением оригинальной ошибки.

Рекомендуется проверять `result.success` и логировать `result.raw` для диагностики.

---

## Практические примеры

### 1) Вход по номиналу в USDT
```python
result = conn.place_futures_order_with_protection(
	symbol="ETHUSDT",
	side="BUY",
	entry_price=3500.0,
	deviation_percent=0.2,          # поставить лимит ниже на 0.2%
	stop_loss_price=3420.0,
	trailing_activation_price=3550.0,
	trailing_callback_percent=0.5,   # 0.5%
	leverage=5,
	notional_usdt=100.0,             # хотим ~100 USDT номинала
	take_profit_price=3600.0,        # опционально
	margin_type="ISOLATED",
	working_type="MARK_PRICE",
	position_side="BOTH",
	verbose=True,
)

if result.success:
	print("OK")
else:
	print("ERROR:", result.message, result.error_code)
```

### 2) Вход от риска на сделку (банк задан явно)
```python
result = conn.place_futures_order_with_protection(
	symbol="ETHUSDT",
	side="SELL",
	entry_price=3500.0,
	deviation_percent=0.15,
	stop_loss_price=3560.0,
	trailing_activation_price=3450.0,
	trailing_callback_percent=0.8,
	leverage=10,
	risk_percent_of_bank=0.5,        # риск 0.5% от банка
	current_bank_usdt=2000.0,        # банк передан явно
	margin_type="ISOLATED",
	verbose=True,
)
```

### 3) Вход от риска на сделку (банк читается из API)
```python
result = conn.place_futures_order_with_protection(
	symbol="BTCUSDT",
	side="BUY",
	entry_price=65000.0,
	deviation_percent=0.1,
	stop_loss_price=64000.0,
	trailing_activation_price=65500.0,
	trailing_callback_percent=0.3,
	leverage=3,
	risk_percent_of_bank=1.0,        # банк будет прочитан через account()
	verbose=True,
)
```

---

## Примечания и лучшие практики

- Для тестов используйте `testnet=True`. Убедитесь, что ключи от тестовой среды, иначе будет ошибка авторизации.
- В Hedge Mode указывайте корректный `position_side` для соответствующей стороны позиции.
- `reduce_only=True` на защитных ордерах предотвращает увеличение позиции защитными ордерами.
- Следите за минимальными ограничениями биржи: маленькие `notional_usdt`/риск могут привести к тому, что после округления ордера будут отвергнуты.
- Для стабильности указывайте разумный `recv_window_ms` (например, 60000) и учитывайте системное время.
- Логи (`verbose=True`) помогают воспроизвести и диагностировать проблемы на проде.

---

## Справка по методам

- `derive_quantity(notional_usdt, entry_price, step_size, min_qty) -> float` — вычисляет `qty` от номинала.
- `derive_quantity_by_risk(bank_usdt, risk_percent, entry_price, stop_loss_price, step_size, min_qty) -> float` — вычисляет `qty` по риску.
- `compute_quantity_from_risk(symbol, entry_price, stop_loss_price, risk_percent_of_bank, balance_type="wallet", verbose=False) -> float` — то же самое, но сам читает баланс.
- `get_usdt_balance(balance_type="wallet") -> float` — возвращает баланс USDT.
- `set_leverage(symbol, leverage)` — устанавливает плечо.
- `set_margin_type(symbol, margin_type="ISOLATED")` — устанавливает тип маржи.
- `place_futures_order_with_protection(...) -> OrderResult` — создаёт комплект ордеров: вход, стоп-лосс, (опционально) тейк-профит и трейлинг-стоп. 