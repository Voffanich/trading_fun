# Конфигурация бота: подробное описание параметров

Документ описывает параметры конфигурационных файлов `config_5m_rm.json`, `config_5m.json`, `config_1h.json`.

## Раздел general
- `db_file_name` (string): имя SQLite-базы сделок. Отдельный файл для разных режимов/ТФ.
- `trading_timeframe` (string): рабочий таймфрейм бота (`1m|5m|15m|1h|4h|1d`).
- `timeframes_used` (string[]): перечень таймфреймов, по которым строятся уровни (в порядке возрастания). Базовый ТФ должен входить в список.
- `all_timeframes` (string[]): все поддерживаемые ТФ (для справки/внутренней логики).
- `basic_candle_depths` (number[]): историческая глубина (по умолчанию) для каждого ТФ (сопоставляется индексно с `all_timeframes`).
- `basic_candle_depth` (object): глубина истории по ТФ, например `{"5m":288, "1h":240, ...}`. Используется в загрузке OHLCV.
- `initial_bank_for_test_stats` (number): банк по умолчанию для оффлайн-статистики (если реальный банк недоступен).
- `use_dynamic_trading_pairs` (boolean): включить динамический список пар по объёму и фильтрам биржи.
- `dynamic_trading_pairs_top_n` (number): брать топ-N UM USDT фьючерсных пар по объёму за 24 часа.
- `use_fast_data` (boolean): включить ускоренный загрузчик свечей `fast_data.py` (кэш, единый `requests.Session`).
- `enable_trade_calc_logging` (boolean): включить подробный консольный/файловый лог расчётов и коннектора.
- `trading_pairs` (string[]): статический список пар (используется, если `use_dynamic_trading_pairs=false`).
- `futures_api_mode` ("classic"|"pm"): режим API для фьючерсов:
  - `classic`: стандартные UM Futures (FAPI, SDK `UMFutures`).
  - `pm`: Portfolio Margin (PAPI, эндпоинты `/papi/...`, заголовок `X-MBX-PORTFOLIO-MARGIN: true`).
- `use_order_manager` (boolean): включить `OrderManager` для размещения/сопровождения ордеров.
- `enable_om_minute_cleanup` (boolean): разрешить минутный цикл зачистки OM. По умолчанию выключено (шум). Если включено — OM будет очищать «хвосты» ордеров по активным символам, не печатая лишней диагностики.
- `use_pm_total_collateral` (boolean): использовать общий баланс (equity = `accountEquity/actualEquity`) в качестве банка в PM-режиме (для фильтров динамических пар и прочих расчётов).
- `dynamic_pairs_bank` (number): банк (в USDT), вычисляется при старте (PM: equity; classic: кошелёк/доступный). Переопределяется автоматически кодом.

## Раздел levels
- `candle_depth` (number): глубина свечей для поиска и анализа уровней на базовом ТФ и выше.
- `basic_density` (number): базовый коэффициент плотности уровня.
- `broken_density_factor` (number): множитель плотности сломанного уровня (обычно < 1.0).
- `upper_level_density_factor` (number): множитель плотности при переходе на старший ТФ.

## Раздел deal_config
- `stop_distance_mode` (string): режим расчёта стопа (`far_level_price|middle_level_price|close_level_price`).
- `stop_distance_modes` (string[]): перечисление допустимых режимов стопа.
- `take_distance_mode` (string): режим расчёта тейка (аналогично стопу).
- `take_distance_modes` (string[]): перечисление допустимых режимов тейка.
- `stop_offset_mode` (string): способ смещения стопа относительно базовой точки (`dist_percentage|lower_atr_x|level_percentage`).
- `take_offset_mode` (string): способ смещения тейка (аналогично).
- `stop_offset_modes` (object): параметры смещения стопа. Пример: `{ "dist_percentage": -30 }` — сдвиг в процентах от расстояния до уровня (знак важен).
- `take_offset_modes` (object): параметры смещения тейка. Пример: `{ "dist_percentage": 30 }`.
- `considering_level_density` (number): порог плотности уровней, ниже которого уровни игнорируются.
- `profit_loss_ratio_min` (number): минимально допустимое соотношение профит/лосс для сделки.
- `profit_loss_ratio_max` (number): максимально допустимое соотношение профит/лосс.
- `take_distance_threshold` (number, %): минимальная дистанция до тейка (в процентах от цены входа) для валидации сделки.
- `stop_distance_threshold` (number, %): минимальная дистанция до стопа (в процентах от цены входа) для валидации сделки.
- `deal_risk_perc_of_bank` (number, %): риск на сделку как доля банка (для расчёта количества по риску).
- `leverage_on` (boolean): включать установку плеча в процессе размещения сделки.
- `leverage` / `max_leverage` (number): плечо по умолчанию / максимальное плечо.
- `deal_comission` (number, %): комиссия, учитываемая в расчёте профит/лосс.
- `comission_count_reverse` (boolean): пересчитывать комиссии в «обратном» режиме (см. код `levels.get_profit_loss_ratio`).

Ограничители сделок:
- `max_one_direction_deals` (number): максимум активных сделок в одну сторону.
- `direction_quantity_diff` (number): допустимая разница в количестве лонгов/шортов.
- `max_deals_total` (number): максимум активных сделок всего.
- `max_deals_pair` (number): максимум активных сделок на одну пару.

Пауза (cooldown):
- `cool_down_check_period` (hours): период, в котором анализируется серия выигрышей/проигрышей (в часах).
- `cool_down_loss_quantity` (number): длина серии (выигрышей/проигрышей, в зависимости от флага), вызывающая паузу.
- `cool_down_length` (hours): длительность паузы (в часах).
- `cool_down_reverse` (boolean): считать серию по выигрышам (true) либо по проигрышам (false).

Валидация индикаторами:
- `indicators_validation` (boolean): включить проверку индикаторов.
- `indicators` (object): целевые уровни/флаги индикаторов (например, `RSI_long`, `RSI_short`).

## Как выбирать банк в PM
- Общий баланс (банк): `accountEquity`/`actualEquity` из `/papi/v1/account`. В коде — `get_usdt_balance("collateral")`.
- Доступный баланс: `totalAvailableBalance` из `/papi/v1/account`. В коде — `get_usdt_balance("available")`.
- Баланс кошелька USDT: `totalWalletBalance`/`umWalletBalance` из `/papi/v1/balance`. В коде — `get_usdt_balance("wallet")`.

## Динамический список пар
Если `use_dynamic_trading_pairs=true`:
1) Получаем топ-N пар по объёму: `/fapi/v1/ticker/24hr` + фильтр UM USDT perpetual.
2) Фильтруем пары по `minNotional` и шагам лота/цены, учитывая:
   - банк (equity в PM, либо кошелёк в classic);
   - риск `deal_risk_perc_of_bank`;
   - минимальную дистанцию до стопа `stop_distance_threshold` и защитный буфер.

## Параметры OrderManager
`order_manager` (object):
- `retries` (number): количество повторов при размещении.
- `backoff_sec` (number[]): интервалы между повторами.
- `poll_interval_sec` (number): интервал опроса при сопровождении.
- `placement_timeout_sec` (number): таймаут на размещение.
- `max_slippage_pct` (number, %): максимально допустимое проскальзывание относительно `markPrice`.
- `unfilled_entry_ttl_sec` (number): TTL незаполненного входного LIMIT (при 0 — не используется).

## Примеры
- PM режим:
```json
{
  "general": {
    "futures_api_mode": "pm",
    "use_pm_total_collateral": true,
    "use_dynamic_trading_pairs": true,
    "enable_om_minute_cleanup": false
  }
}
```

- Classic режим:
```json
{
  "general": {
    "futures_api_mode": "classic",
    "use_dynamic_trading_pairs": false
  }
}
```

