-- Variant metrics summary table
CREATE OR REPLACE TABLE `instacart.variant_metrics` AS

SELECT
  variant,
  COUNT(*) AS users,
  SUM(converted) AS converters,
  SAFE_DIVIDE(SUM(converted), COUNT(*)) AS conversion_rate,
  AVG(items_in_window) AS arpu,
  VAR_SAMP(items_in_window) AS arpu_var
FROM `instacart.user_outcomes`
GROUP BY variant;

SELECT * FROM `instacart.variant_metrics`; -- view table with summary metrics by variant

-- calculate absolute, relative lift and z-test on conversion rate
WITH m AS (
  SELECT * FROM `instacart.variant_metrics`
),
p AS (
  SELECT
    MAX(CASE WHEN variant='A' THEN conversion_rate END) AS cr_a,
    MAX(CASE WHEN variant='B' THEN conversion_rate END) AS cr_b,
    MAX(CASE WHEN variant='A' THEN users END)           AS n_a,
    MAX(CASE WHEN variant='B' THEN users END)           AS n_b
  FROM m
)
-- view coversion rates by variant, relative and absolute lift and z_score
SELECT
  cr_a,
  cr_b,
  cr_b - cr_a AS abs_lift,
  SAFE_DIVIDE(cr_b - cr_a, cr_a) AS rel_lift,
  (cr_b - cr_a) /
  SQRT( (cr_a*(1-cr_a))/n_a + (cr_b*(1-cr_b))/n_b ) AS z_score
FROM p;

-- look at the proxy for ARPU and run t-test
WITH m AS (
  SELECT * FROM `instacart.variant_metrics`
),
p AS (
  SELECT
    MAX(CASE WHEN variant='A' THEN arpu END)     AS m_a,
    MAX(CASE WHEN variant='B' THEN arpu END)     AS m_b,
    MAX(CASE WHEN variant='A' THEN arpu_var END) AS v_a,
    MAX(CASE WHEN variant='B' THEN arpu_var END) AS v_b,
    MAX(CASE WHEN variant='A' THEN users END)    AS n_a,
    MAX(CASE WHEN variant='B' THEN users END)    AS n_b
  FROM m
)
-- look at the average items per user (proxy ARPU) per variant, difference in means and test statistic
SELECT
  m_a,
  m_b,
  m_b - m_a AS diff,
  (m_b - m_a) / SQRT( (v_a/n_a) + (v_b/n_b) ) AS t_stat
FROM p;

-- Significance test for Day 14 retention
WITH m AS (
  SELECT variant,
         COUNT(*) AS n,
         SUM(retained_d14) AS r
  FROM `instacart.user_outcomes`
  GROUP BY variant
),
p AS (
  SELECT
    MAX(CASE WHEN variant='A' THEN r END) / MAX(CASE WHEN variant='A' THEN n END) AS r_a,
    MAX(CASE WHEN variant='B' THEN r END) / MAX(CASE WHEN variant='B' THEN n END) AS r_b,
    MAX(CASE WHEN variant='A' THEN n END) AS n_a,
    MAX(CASE WHEN variant='B' THEN n END) AS n_b
  FROM m
)
SELECT
  r_a,
  r_b,
  r_b - r_a AS abs_lift,
  SAFE_DIVIDE(r_b - r_a, r_a) AS rel_lift,
  (r_b - r_a) /
  SQRT( (r_a*(1-r_a))/n_a + (r_b*(1-r_b))/n_b ) AS z_score
FROM p;

