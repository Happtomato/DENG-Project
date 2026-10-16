-- Row counts and source readiness
SELECT master_status, master_source, count(*) FROM product GROUP BY 1,2;
SELECT r.name, count(*) AS observations, min(ph.price_date), max(ph.price_date)
FROM price_history ph JOIN retailer_product rp USING(retailer_product_id)
JOIN retailer r USING(retailer_id) GROUP BY r.name;
SELECT retailer_code,status,reason,count(*) FROM raw_record GROUP BY 1,2,3;
SELECT * FROM matching_review ORDER BY created_at;
-- The view stays empty until both sellers have verified observations on the same day.
SELECT * FROM digitec_mediamarkt_comparison ORDER BY price_date,product_id;
-- Platform observations also expose third-party and unknown sellers.
SELECT * FROM daily_price_observation ORDER BY price_date,product_id;
-- These must both return zero.
SELECT count(*) AS invalid_prices FROM price_history WHERE price_chf IS NULL OR price_chf<=0;
SELECT observation_key,count(*) FROM price_history WHERE observation_key IS NOT NULL
GROUP BY observation_key HAVING count(*)>1;
