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
--             best_price_perc REAL,
--             worst_price_perc REAL,
--             current_price REAL,
--             current_price_perc REAL,
--             status TEXT NOT NULL,
--             finish_time TEXT,
--             indicators TEXT);

-- INSERT INTO deals (datetime,
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
--             best_price_perc,
--             worst_price_perc,
                     
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
--             ROUND(ABS(best_price - entry_price) / entry_price * 100, 2),
--             ROUND(ABS(worst_price - entry_price) / entry_price * 100, 2),
--             status,
--             indicators
--     FROM deals_old;

-- delete from sqlite_sequence where name='deals';

-- DELETE FROM deals;

-- DROP TABLE deals_old;

-- DELETE FROM deals 
-- WHERE pair IS 'PEPEUSDT' AND status IS 'active';

-- DELETE FROM deals 
-- WHERE pair IS 'LUNCUSDT' AND status IS 'active';

-- ALTER TABLE deals RENAME TO deals_old;
-- ALTER TABLE deals_new RENAME TO deals;

-- DELETE FROM deals WHERE best_price IS NULL;

-- UPDATE deals
-- SET worst_price = 0.9
-- WHERE deal_id = 560;

-- SELECT * FROM deals
-- WHERE status = 'active';

-- SELECT * FROM deals
-- WHERE status <> 'active';

-- SELECT pair FROM deals
-- WHERE status = 'active'
-- GROUP BY pair;

-- UPDATE deals
-- SET best_price_perc = ROUND(ABS(best_price - entry_price) / entry_price * 100, 2)
-- WHERE best_price_perc IS NULL;

-- UPDATE deals
-- SET worst_price_perc = ROUND(ABS(worst_price - entry_price) / entry_price * 100, 2)
-- WHERE worst_price_perc IS NULL;

-- SELECT * FROM deals
-- WHERE worst_price_perc IS NULL OR best_price_perc IS NULL;

-- SELECT SUM(2 / profit_loss) as profit, COUNT(*) as profitable_deals, profit / profitable_deals AS average_profit FROM deals
-- WHERE status = "loss" AND strftime("%Y-%m-%d", datetime) = "2023-06-16"

-- UPDATE deals
-- SET profit_loss = ROUND((take_dist_perc - 0.04*2)/(stop_dist_perc + 0.04*2), 2)
-- WHERE status <> 'active';

-- UPDATE deals
-- SET profit_loss = ROUND((take_dist_perc + 0.08*2)/(stop_dist_perc - 0.08*2), 2)
-- WHERE status <> 'active';

-- SELECT count(*) FROM deals
-- WHERE status = 'active' AND pair = 'LINAUSDT'

SELECT finish_time FROM deals
WHERE status = "win" AND strftime("%Y-%m-%d %H:%M:%S", datetime) > "2023-08-23 00:05:00"
ORDER BY finish_time


