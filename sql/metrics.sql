-- Each measure is calculated from the classified ledger. Quarantined rows are excluded.
DROP VIEW IF EXISTS monthly_metrics;
CREATE VIEW monthly_metrics AS
SELECT month,
       SUM(CASE WHEN classification = 'product_sale' THEN amount ELSE 0 END) AS gross_product_sales,
       SUM(CASE WHEN classification = 'credit' THEN amount ELSE 0 END) AS credits,
       SUM(CASE WHEN classification = 'adjustment' THEN amount ELSE 0 END) AS adjustments,
       SUM(amount) AS net_revenue,
       COUNT(DISTINCT CASE WHEN classification = 'product_sale' THEN invoice END) AS orders,
       COUNT(DISTINCT CASE WHEN classification = 'product_sale' AND customer <> 'UNKNOWN' THEN customer END) AS known_active_customers,
       SUM(CASE WHEN classification = 'product_sale' AND customer = 'UNKNOWN' THEN amount ELSE 0 END) AS unidentified_gross_sales
FROM fact_transactions
WHERE classification <> 'quarantine'
GROUP BY month;

DROP VIEW IF EXISTS customer_metrics;
CREATE VIEW customer_metrics AS
SELECT customer,
       SUM(amount) AS net_revenue,
       SUM(CASE WHEN classification = 'product_sale' THEN amount ELSE 0 END) AS gross_sales,
       COUNT(DISTINCT CASE WHEN classification = 'product_sale' THEN invoice END) AS orders,
       MIN(CASE WHEN classification = 'product_sale' THEN date END) AS first_purchase,
       MAX(CASE WHEN classification = 'product_sale' THEN date END) AS last_purchase
FROM fact_transactions
WHERE classification <> 'quarantine' AND customer <> 'UNKNOWN'
GROUP BY customer;

DROP VIEW IF EXISTS product_metrics;
CREATE VIEW product_metrics AS
SELECT product,
       SUM(CASE WHEN classification = 'product_sale' THEN quantity ELSE 0 END) AS sold_units,
       SUM(CASE WHEN classification = 'product_sale' THEN amount ELSE 0 END) AS gross_sales,
       -SUM(CASE WHEN classification = 'credit' THEN amount ELSE 0 END) AS credited_value,
       SUM(amount) AS net_revenue
FROM fact_transactions
WHERE classification <> 'quarantine' AND is_product = 1
GROUP BY product;
