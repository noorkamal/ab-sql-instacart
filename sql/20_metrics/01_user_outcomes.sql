-- Create a table to capture user outcomes such as converted, proxy for ARPU and retention
CREATE OR REPLACE TABLE `instacart.user_outcomes` AS

WITH win AS (
  SELECT * FROM `instacart.events_windowed`
),
-- Count items per order. Since we don't have prices we will use this as a proxy for Average Revenue Per User
line_items AS (
  SELECT
    order_id,
    COUNT(*) AS items
  FROM `instacart.order_products_prior`
  GROUP BY order_id
),
-- Aggregate per user inside the 28-day window
agg AS (
  SELECT
    w.user_id,
    ANY_VALUE(w.variant) AS variant,
    ANY_VALUE(w.assigned_at) AS assigned_at,
    COUNT(DISTINCT w.order_id) AS orders_in_window, -- number of orders in window
    SUM(COALESCE(li.items, 0)) AS items_in_window, -- number of items across all orders in window
    COUNTIF(w.pseudo_order_date < DATE_ADD(w.assigned_at, INTERVAL 14 DAY)) AS orders_before_d14 -- number of orders before the 14 day mark in the window
  FROM win w
  LEFT JOIN line_items li
    ON li.order_id = w.order_id
  GROUP BY w.user_id
)
-- Calculate metrics for APRU proxy (number of items ordered), converted and retained by day 14
SELECT
  a.user_id,
  a.variant,
  a.assigned_at,
  IFNULL(ag.orders_in_window, 0) AS orders_in_window, 
  IFNULL(ag.items_in_window, 0)  AS items_in_window, 
  CASE WHEN IFNULL(ag.orders_in_window, 0) >= 1 THEN 1 ELSE 0 END AS converted, -- if users placed an order during the window
  CASE WHEN IFNULL(ag.orders_before_d14, 0) >= 1 THEN 1 ELSE 0 END AS retained_d14 -- if users placed an order before day 14 of window
FROM `instacart.assignments` a
LEFT JOIN agg ag
  ON ag.user_id = a.user_id;