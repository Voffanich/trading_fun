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

INSERT INTO deals (datetime,
            pair,
            timeframe,
            direction,
            profit_loss,
            entry_price,
            take_price,
            stop_price,
            take_dist_perc,
            stop_dist_perc,
            best_price,
            worst_price, 
            best_price_perc,
            worst_price_perc,
                     
            status,            
            indicators)
    SELECT 
            datetime,
            pair,
            timeframe,
            direction,
            profit_loss,
            entry_price,
            take_price,
            stop_price,
            take_dist_perc,
            stop_dist_perc,
            best_price,
            worst_price,
            ROUND(ABS(best_price - entry_price) / entry_price * 100, 2),
            ROUND(ABS(worst_price - entry_price) / entry_price * 100, 2),
            status,
            indicators
    FROM deals_old;

-- delete from sqlite_sequence where name='deals';

-- DELETE FROM deals;

-- DROP TABLE deals_new;

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
