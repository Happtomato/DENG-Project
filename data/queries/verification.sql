SELECT 'products' AS metric,count(*) FROM product
UNION ALL SELECT 'listings',count(*) FROM retailer_product
UNION ALL SELECT 'observations',count(*) FROM price_history;
SELECT status,reason,count(*) FROM raw_import GROUP BY 1,2 ORDER BY 1,2;
SELECT product_name,category,platform,seller_name,price_chf,observed_at,raw_path,
       ssd_capacity_gb,ssd_chf_per_gb
FROM hardware_prices ORDER BY category,product_name,observed_at;
-- Both checks must be empty/zero; that alone does NOT prove data was loaded.
SELECT count(*) AS invalid_prices FROM price_history WHERE price_chf<=0 OR currency<>'CHF';
SELECT retailer_product_id,collected_at,count(*) FROM price_history GROUP BY 1,2 HAVING count(*)>1;
