/* we will simulate a case where we create pseudo order dates using the days from prior order given.
Using a fixed base date of '2017-01-01' assume that everyones first order took place on this date. 
*/

-- days since prior order is null for the first order, replace with zero
CREATE OR REPLACE TABLE `instacart.user_orders_pseudodate` AS
WITH ordered AS (
  SELECT
    o.user_id,
    o.order_id,
    o.order_number,
    COALESCE(o.days_since_prior_order, 0) AS days_since_prior_order
  FROM `instacart.orders` o
),
-- For each order, calculate cumulative days since that user's first order
cum AS (
  SELECT
    user_id,
    order_id,
    order_number,
    SUM(days_since_prior_order) OVER (
      PARTITION BY user_id
      ORDER BY order_number
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS days_since_first
  FROM ordered
)
-- Anchor everyone’s first order to a fixed base date, get pseudo order dates by adding the cumulative days since first order
SELECT
  user_id,
  order_id,
  order_number,
  DATE '2017-01-01' + INTERVAL CAST(days_since_first AS INT64) DAY AS pseudo_order_date
FROM cum;