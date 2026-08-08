SELECT
    SUBSTR(order_timestamp, 1, 10) AS order_date,
    product_id,
    currency,
    COUNT(DISTINCT order_id) AS total_orders,
    SUM(quantity) AS units_sold,
    ROUND(SUM(quantity * unit_price_cents) / 100.0, 2) AS gross_revenue
FROM orders
GROUP BY
    SUBSTR(order_timestamp, 1, 10),
    product_id,
    currency;
