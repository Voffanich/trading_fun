

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

--## reverse strategy 2% risk per deal

SELECT  profit_table.date, profit - loss as day_result, profit, profitable_deals, average_profit, loss, lost_deals, average_loss FROM 
(SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(2 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))), 3) AS profit, COUNT(*) AS profitable_deals, 
    ROUND(SUM(2 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))) / COUNT(*), 3) AS average_profit FROM deals
WHERE status = 'loss'
GROUP BY date) as profit_table
INNER JOIN 
(SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 2 AS loss, COUNT(*) AS lost_deals, 
    ROUND(COUNT(*) * 2 / COUNT(*), 3) AS average_loss FROM deals
WHERE status = 'win' 
GROUP BY date) as loss_table 
ON profit_table.date = loss_table.date;

SELECT SUM(day_result) AS total_reverse_strategy_2p from 
(SELECT  profit_table.date, profit - loss as day_result, profit, profitable_deals, average_profit, loss, lost_deals, average_loss FROM 
(SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(2 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))), 3) AS profit, COUNT(*) AS profitable_deals, 
    ROUND(SUM(2 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))) / COUNT(*), 3) AS average_profit FROM deals
WHERE status = 'loss'
GROUP BY date) as profit_table
INNER JOIN 
(SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 2 AS loss, COUNT(*) AS lost_deals, 
    ROUND(COUNT(*) * 2 / COUNT(*), 3) AS average_loss FROM deals
WHERE status = 'win'
GROUP BY date) as loss_table 
ON profit_table.date = loss_table.date);

SELECT ROUND(SUM(2 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))), 3) as total_profit_2p FROM deals
WHERE status = 'loss';

SELECT COUNT(*) * 2 as total_loss_2p FROM deals
WHERE status = 'win';

--## reverse strategy 1% risk per deal

SELECT  profit_table.date, profit - loss as day_result, profit, profitable_deals, average_profit, loss, lost_deals, average_loss FROM 
(SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(1 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))), 3) AS profit, COUNT(*) AS profitable_deals, 
    ROUND(SUM(1 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))) / COUNT(*), 3) AS average_profit FROM deals
WHERE status = 'loss'
GROUP BY date) as profit_table
INNER JOIN 
(SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 1 AS loss, COUNT(*) AS lost_deals, 
    ROUND(COUNT(*) * 1 / COUNT(*), 3) AS average_loss FROM deals
WHERE status = 'win' 
GROUP BY date) as loss_table 
ON profit_table.date = loss_table.date;

SELECT SUM(day_result) AS total_reverse_strategy_1p from 
(SELECT  profit_table.date, profit - loss as day_result, profit, profitable_deals, average_profit, loss, lost_deals, average_loss FROM 
(SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(1 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))), 3) AS profit, COUNT(*) AS profitable_deals, 
    ROUND(SUM(1 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))) / COUNT(*), 3) AS average_profit FROM deals
WHERE status = 'loss'
GROUP BY date) as profit_table
INNER JOIN 
(SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 1 AS loss, COUNT(*) AS lost_deals, 
    ROUND(COUNT(*) * 1 / COUNT(*), 3) AS average_loss FROM deals
WHERE status = 'win'
GROUP BY date) as loss_table 
ON profit_table.date = loss_table.date);

SELECT ROUND(SUM(1 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))), 3) as total_profit_1p FROM deals
WHERE status = 'loss';

SELECT COUNT(*) * 1 as total_loss_1p FROM deals
WHERE status = 'win';

--## reverse strategy 1.5% risk per deal

SELECT  profit_table.date, profit - loss as day_result, profit, profitable_deals, average_profit, loss, lost_deals, average_loss FROM 
(SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(1.5 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))), 3) AS profit, COUNT(*) AS profitable_deals, 
    ROUND(SUM(1.5 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))) / COUNT(*), 3) AS average_profit FROM deals
WHERE status = 'loss'
GROUP BY date) as profit_table
INNER JOIN 
(SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 1.5 AS loss, COUNT(*) AS lost_deals, 
    ROUND(COUNT(*) * 1.5 / COUNT(*), 3) AS average_loss FROM deals
WHERE status = 'win' 
GROUP BY date) as loss_table 
ON profit_table.date = loss_table.date;

SELECT SUM(day_result) AS total_reverse_strategy_15p from 
(SELECT  profit_table.date, profit - loss as day_result, profit, profitable_deals, average_profit, loss, lost_deals, average_loss FROM 
(SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(1.5 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))), 3) AS profit, COUNT(*) AS profitable_deals, 
    ROUND(SUM(1.5 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))) / COUNT(*), 3) AS average_profit FROM deals
WHERE status = 'loss'
GROUP BY date) as profit_table
INNER JOIN 
(SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 1.5 AS loss, COUNT(*) AS lost_deals, 
    ROUND(COUNT(*) * 1.5 / COUNT(*), 3) AS average_loss FROM deals
WHERE status = 'win'
GROUP BY date) as loss_table 
ON profit_table.date = loss_table.date);

SELECT ROUND(SUM(1.5 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))), 3) as total_profit_15p FROM deals
WHERE status = 'loss';

SELECT COUNT(*) * 1.5 as total_loss_15p FROM deals
WHERE status = 'win';


-- ## direct strategy

SELECT  profit_table.date, profit - loss as day_result, profit, profitable_deals, average_profit, loss, lost_deals, average_loss FROM 
(SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(2 * profit_loss), 3) AS profit, COUNT(*) AS profitable_deals, 
    ROUND(SUM(2 * profit_loss) / COUNT(*), 3) AS average_profit FROM deals
WHERE status = 'win' 
GROUP BY date) as profit_table
INNER JOIN 
(SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 2 AS loss, COUNT(*) AS lost_deals, 
    ROUND(COUNT(*) * 2 / COUNT(*), 3) AS average_loss FROM deals
WHERE status = 'loss' 
GROUP BY date) as loss_table 
ON profit_table.date = loss_table.date;

SELECT SUM(day_result) AS total_direct_strategy from (
SELECT  profit_table.date, profit - loss as day_result, profit, profitable_deals, average_profit, loss, lost_deals, average_loss FROM 
(SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(2 * profit_loss), 3) AS profit, COUNT(*) AS profitable_deals, 
    ROUND(SUM(2 * profit_loss) / COUNT(*), 3) AS average_profit FROM deals
WHERE status = 'win'
GROUP BY date) as profit_table
INNER JOIN 
(SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 2 AS loss, COUNT(*) AS lost_deals, 
    ROUND(COUNT(*) * 2 / COUNT(*), 3) AS average_loss FROM deals
WHERE status = 'loss' 
GROUP BY date) as loss_table 
ON profit_table.date = loss_table.date);

-- ## data for PL > 15

-- SELECT COUNT(*) as PL_bigger_15 FROM deals 
-- WHERE profit_loss > 15;

-- SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(2 * profit_loss), 3) AS profit, COUNT(*) AS profitable_deals, 
--     ROUND(SUM(2 * profit_loss) / COUNT(*), 3) AS average_profit FROM deals
-- WHERE status = 'win' AND profit_loss > 15
-- GROUP BY date;

-- SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 2 AS loss, COUNT(*) AS lost_deals, 
--     ROUND(COUNT(*) * 2 / COUNT(*), 3) AS average_loss FROM deals
-- WHERE status = 'loss' AND profit_loss > 15
-- GROUP BY date;

-- SELECT SUM(profit) from (
-- SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(2 * profit_loss), 3) AS profit, COUNT(*) AS profitable_deals, 
--     ROUND(SUM(2 * profit_loss) / COUNT(*), 3) AS average_profit FROM deals
-- WHERE status = 'win' AND profit_loss > 15
-- GROUP BY date);

-- SELECT SUM(loss) from (
-- SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 2 AS loss, COUNT(*) AS lost_deals, 
--     ROUND(COUNT(*) * 2 / COUNT(*), 3) AS average_loss FROM deals
-- WHERE status = 'loss' AND profit_loss > 15
-- GROUP BY date);

-- list of good pairs on 2023-06-30 >3
--('ATOMUSDT', 'AVAXUSDT', 'BNBUSDT', 'BTCUSDT', 'ETCUSDT', 'ETHUSDT', 'JOEUSDT', 'LUNAUSDT', 'MASKUSDT', 'NEARUSDT', 'PEPEUSDT', 'SOLUSDT', 'TRXUSDT')
-- list of good pairs on 2023-07-10 >4
--('ATOMUSDT', 'BNBUSDT', 'BTCUSDT', 'PEPEUSDT', 'TRXUSDT')


-- list of bad pairs on 2023-06-30
--('ADAUSDT', 'APTUUSDT', 'DOGEUSDT', 'EDUUSDT', 'LINAUSDT', 'SUSHI')
-- list of bad pairs on 2023-06-10 <2.5
--('APTUUSDT', 'EDUUSDT', 'ETCUSDT', 'GALAUSDT', 'JOEUSDT', 'LINAUSDT', 'LUNCUSDT', 'MATICUSDT', 'NEARUSDT', 'SOLUSDT', 'SUIUSDT', 'SUSHIUSDT')

--## reverse strategy with good pairs

SELECT  profit_table.date, profit - loss as day_result, profit, profitable_deals, average_profit, loss, lost_deals, average_loss FROM 
(SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(2 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))), 3) AS profit, COUNT(*) AS profitable_deals, 
    ROUND(SUM(2 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))) / COUNT(*), 3) AS average_profit FROM deals
WHERE status = 'loss' AND pair IN ('ATOMUSDT', 'BNBUSDT', 'BTCUSDT', 'PEPEUSDT', 'TRXUSDT')
GROUP BY date) as profit_table
INNER JOIN 
(SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 2 AS loss, COUNT(*) AS lost_deals, 
    ROUND(COUNT(*) * 2 / COUNT(*), 3) AS average_loss FROM deals
WHERE status = 'win' AND pair IN ('ATOMUSDT', 'BNBUSDT', 'BTCUSDT', 'PEPEUSDT', 'TRXUSDT')
GROUP BY date) as loss_table 
ON profit_table.date = loss_table.date;

SELECT SUM(day_result) AS good_reverse_strategy from 
(SELECT  profit_table.date, profit - loss as day_result, profit, profitable_deals, average_profit, loss, lost_deals, average_loss FROM 
(SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(2 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))), 3) AS profit, COUNT(*) AS profitable_deals, 
    ROUND(SUM(2 * ((stop_dist_perc - 0.08)/(take_dist_perc + 0.08))) / COUNT(*), 3) AS average_profit FROM deals
WHERE status = 'loss' AND pair IN ('ATOMUSDT', 'BNBUSDT', 'BTCUSDT', 'PEPEUSDT', 'TRXUSDT')
GROUP BY date) as profit_table
INNER JOIN 
(SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 2 AS loss, COUNT(*) AS lost_deals, 
    ROUND(COUNT(*) * 2 / COUNT(*), 3) AS average_loss FROM deals
WHERE status = 'win' AND pair IN ('ATOMUSDT', 'BNBUSDT', 'BTCUSDT', 'PEPEUSDT', 'TRXUSDT')
GROUP BY date) as loss_table 
ON profit_table.date = loss_table.date);

-- ## direct strategy with good pairs

SELECT  profit_table.date, profit - loss as day_result, profit, profitable_deals, average_profit, loss, lost_deals, average_loss FROM 
(SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(2 * profit_loss), 3) AS profit, COUNT(*) AS profitable_deals, 
    ROUND(SUM(2 * profit_loss) / COUNT(*), 3) AS average_profit FROM deals
WHERE status = 'win' AND pair IN ('APTUUSDT', 'EDUUSDT', 'ETCUSDT', 'GALAUSDT', 'JOEUSDT', 'LINAUSDT', 'LUNCUSDT', 'MATICUSDT', 'NEARUSDT', 'SOLUSDT', 'SUIUSDT', 'SUSHIUSDT')
GROUP BY date) as profit_table
INNER JOIN 
(SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 2 AS loss, COUNT(*) AS lost_deals, 
    ROUND(COUNT(*) * 2 / COUNT(*), 3) AS average_loss FROM deals
WHERE status = 'loss' AND pair IN ('APTUUSDT', 'EDUUSDT', 'ETCUSDT', 'GALAUSDT', 'JOEUSDT', 'LINAUSDT', 'LUNCUSDT', 'MATICUSDT', 'NEARUSDT', 'SOLUSDT', 'SUIUSDT', 'SUSHIUSDT')
GROUP BY date) as loss_table 
ON profit_table.date = loss_table.date;

SELECT SUM(day_result) AS good_direct_strategy from (
SELECT  profit_table.date, profit - loss as day_result, profit, profitable_deals, average_profit, loss, lost_deals, average_loss FROM 
(SELECT strftime('%Y-%m-%d', datetime) AS date, ROUND(SUM(2 * profit_loss), 3) AS profit, COUNT(*) AS profitable_deals, 
    ROUND(SUM(2 * profit_loss) / COUNT(*), 3) AS average_profit FROM deals
WHERE status = 'win' AND pair IN ('APTUUSDT', 'EDUUSDT', 'ETCUSDT', 'GALAUSDT', 'JOEUSDT', 'LINAUSDT', 'LUNCUSDT', 'MATICUSDT', 'NEARUSDT', 'SOLUSDT', 'SUIUSDT', 'SUSHIUSDT')
GROUP BY date) as profit_table
INNER JOIN 
(SELECT strftime('%Y-%m-%d', datetime) AS date, COUNT(*) * 2 AS loss, COUNT(*) AS lost_deals, 
    ROUND(COUNT(*) * 2 / COUNT(*), 3) AS average_loss FROM deals
WHERE status = 'loss' AND pair IN ('APTUUSDT', 'EDUUSDT', 'ETCUSDT', 'GALAUSDT', 'JOEUSDT', 'LINAUSDT', 'LUNCUSDT', 'MATICUSDT', 'NEARUSDT', 'SOLUSDT', 'SUIUSDT', 'SUSHIUSDT')
GROUP BY date) as loss_table 
ON profit_table.date = loss_table.date);