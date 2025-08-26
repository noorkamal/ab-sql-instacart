
-- set assignment date as 2017-07-01 and a 28 day window will be considered
DECLARE assign_date DATE DEFAULT DATE('2017-07-01');

-- create table assignments to randomly assign users to A/B
CREATE OR REPLACE TABLE `instacart.assignments` AS
SELECT 
  user_id,
  CASE WHEN MOD(ABS(FARM_FINGERPRINT(CAST(user_id AS STRING))), 2) = 0 
       THEN 'A' ELSE 'B' END AS variant,
  assign_date AS assigned_at
FROM `instacart.orders`
GROUP BY user_id;

-- row count
SELECT COUNT(*) AS users FROM `instacart.assignments`;

-- split by variant, want to sure equal split of users between variants
SELECT variant, COUNT(*) AS n_users,
       1.0*COUNT(*)/SUM(COUNT(*)) OVER() as pct_users
FROM `instacart.assignments`
GROUP BY variant;
