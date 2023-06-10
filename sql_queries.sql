-- CREATE TABLE IF NOT EXISTS deals_new (
--             deal_id INTEGER PRIMARY KEY AUTOINCREMENT,
--             datetime TEXT NOT NULL,
--             pair TEXT NOT NULL,
--             timeframe TEXT NOT NULL,
--             direction TEXT NOT NULL,
--             profit_loss REAL NOT NULL,
--             entry_price REAL NOT NULL,
--             take_price REAL NOT NULL,
--             stop_price REAL NOT NULL,
--             take_dist_perc REAL NOT NULL,
--             stop_dist_perc REAL NOT NULL,
--             best_price REAL,
--             worst_price REAL,            
--             status TEXT NOT NULL,
--             indicators TEXT);

-- INSERT INTO deals_new ( datetime,
--             pair,
--             timeframe,
--             direction,
--             profit_loss,
--             entry_price,
--             take_price,
--             stop_price,
--             take_dist_perc,
--             stop_dist_perc,
--             best_price,
--             worst_price,            
--             status,
--             indicators)
--     SELECT 
--             datetime,
--             pair,
--             timeframe,
--             direction,
--             profit_loss,
--             entry_price,
--             take_price,
--             stop_price,
--             take_dist_perc,
--             stop_dist_perc,
--             best_price,
--             worst_price,            
--             status,
--             indicators
--     FROM deals 

-- ALTER TABLE deals RENAME TO deals_olв

-- DELETE FROM deals WHERE best_price IS NULL;

-- UPDATE deals
-- SET worst_price = 0.9
-- WHERE deal_id = 560;

-- SELECT * FROM deals
-- WHERE status = 'active';

-- SELECT * FROM deals
-- WHERE status <> 'active';

SELECT status, COUNT(status) FROM deals
GROUP BY status;

-- SELECT pair, count(pair) AS deals_cuantity, avg(stop_dist_perc) AS ave_loss_perc FROM deals
-- WHERE status = 'loss'
-- GROUP BY pair
-- ORDER BY avg(stop_dist_perc) DESC


-- SELECT pair, ((best_price - take_price) / take_price * 100) AS left_to_take, 
-- ((worst_price - stop_price) / take_price * 100) AS left_to_stop, take_dist_perc, stop_dist_perc
-- FROM deals
-- WHERE status = 'active'

-- DEALS QUANTITY BY DAY
-- SELECT strftime('%Y-%m-%d', datetime) AS date, count(*) AS deal_quantity FROM deals
-- GROUP BY date
-- ORDER BY date

-- DEALS QUANTITY BY DAY WITH LOSS AND WIN STATS
SELECT strftime('%Y-%m-%d', datetime) AS date, count(*) AS deal_quantity,
  SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) AS wins,
  SUM(CASE WHEN status = 'loss' THEN 1 ELSE 0 END) AS losses,
  count(*) - SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) - SUM(CASE WHEN status = 'loss' THEN 1 ELSE 0 END) as active_deals
FROM deals
GROUP BY date
ORDER BY date;

-- SELECT * FROM deals
-- WHERE status <> 'active' AND strftime('%Y-%m-%d', datetime) = '2023-06-08';

SELECT * FROM deals
WHERE status <> 'active';