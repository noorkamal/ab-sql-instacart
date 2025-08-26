/* Consider an analysis window of 28 days. */
DECLARE window_days INT64 DEFAULT 28;

-- For each user we only keep orders whose pseudo order date falls within the analysis window (28 days from assigned date)
CREATE OR REPLACE TABLE `instacart.events_windowed` AS
WITH 
cohort AS (
  SELECT user_id, variant, assigned_at
  FROM `instacart.assignments`
),
win AS (
  SELECT
    c.user_id,
    c.variant,
    c.assigned_at,
    uop.order_id,
    uop.pseudo_order_date
  FROM cohort c
  JOIN `instacart.user_orders_pseudodate` uop
    USING (user_id)
  WHERE uop.pseudo_order_date >= c.assigned_at
    AND uop.pseudo_order_date < DATE_ADD(c.assigned_at, INTERVAL window_days DAY)
)

SELECT * FROM win;

-- Check how many users have at least one order in the window
SELECT COUNT(DISTINCT user_id) AS users_with_orders
FROM `instacart.events_windowed`;

-- Distribution of users by variant
SELECT variant, COUNT(DISTINCT user_id) AS users_with_orders
FROM `instacart.events_windowed`
GROUP BY variant;

