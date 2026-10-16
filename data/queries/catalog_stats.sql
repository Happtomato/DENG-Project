-- Read-only catalogue audit. Run with psql; counts describe persisted evidence,
-- not all discovered URLs in data/catalog/mediamarkt.json.
\echo '1. Products, offers, observations, earliest/latest observations'
SELECT (SELECT count(*) FROM product) AS products,
       (SELECT count(*) FROM retailer_product) AS offers,
       (SELECT count(*) FROM price_history) AS observations,
       min(collected_at) AS first_observed_at,
       max(collected_at) AS last_observed_at
FROM price_history;

\echo '2. Products, offers and observations by category'
SELECT c.name AS category, count(DISTINCT p.product_id) AS products,
       count(DISTINCT rp.retailer_product_id) AS offers,
       count(ph.price_id) AS observations
FROM category c JOIN product p USING(category_id)
LEFT JOIN retailer_product rp USING(product_id)
LEFT JOIN price_history ph USING(retailer_product_id)
GROUP BY c.name ORDER BY c.name;

\echo '3. Brands per category; historical out-of-scope brands remain visible'
SELECT c.name AS category, b.name AS brand, count(DISTINCT p.product_id) AS products
FROM product p JOIN category c USING(category_id) JOIN brand b USING(brand_id)
GROUP BY c.name,b.name ORDER BY c.name,b.name;

\echo '4. Retailer platform and actual seller are separate'
SELECT r.name AS platform, coalesce(nullif(btrim(ph.seller_name),''),'UNKNOWN') AS actual_seller,
       count(DISTINCT rp.retailer_product_id) AS offers, count(*) AS observations
FROM price_history ph JOIN retailer_product rp USING(retailer_product_id)
JOIN retailer r USING(retailer_id)
GROUP BY r.name,coalesce(nullif(btrim(ph.seller_name),''),'UNKNOWN')
ORDER BY platform,actual_seller;

\echo '5. Observations per local day and category'
SELECT (ph.collected_at AT TIME ZONE 'Europe/Zurich')::date AS observation_day,
       c.name AS category, count(*) AS observations,
       count(DISTINCT rp.retailer_product_id) AS distinct_offers
FROM price_history ph JOIN retailer_product rp USING(retailer_product_id)
JOIN product p USING(product_id) JOIN category c USING(category_id)
GROUP BY 1,2 ORDER BY 1,2;

\echo '6. Observations per product and current latest price'
SELECT p.product_id, p.product_name, rp.retailer_sku,
       count(ph.price_id) AS observations,
       min(ph.collected_at) AS first_observed_at,
       max(ph.collected_at) AS last_observed_at,
       (array_agg(ph.price_chf ORDER BY ph.collected_at DESC) FILTER (WHERE ph.price_id IS NOT NULL))[1] AS latest_price_chf
FROM product p JOIN retailer_product rp USING(product_id)
LEFT JOIN price_history ph USING(retailer_product_id)
GROUP BY p.product_id,p.product_name,rp.retailer_sku ORDER BY p.product_id;

\echo '7. Products without a valid CHF price; missing identifiers and details'
SELECT count(*) FILTER (WHERE NOT EXISTS (
           SELECT 1 FROM retailer_product rp JOIN price_history ph USING(retailer_product_id)
           WHERE rp.product_id=p.product_id AND ph.currency='CHF' AND ph.price_chf>0)) AS products_without_valid_price,
       count(*) FILTER (WHERE p.ean IS NULL AND p.mpn IS NULL) AS products_without_ean_and_mpn,
       count(*) FILTER (WHERE (c.name='GPU' AND gd.product_id IS NULL)
                         OR (c.name='RAM' AND rd.product_id IS NULL)
                         OR (c.name='SSD' AND sd.product_id IS NULL)) AS products_without_category_details
FROM product p JOIN category c USING(category_id)
LEFT JOIN gpu_details gd USING(product_id)
LEFT JOIN ram_details rd USING(product_id)
LEFT JOIN ssd_details sd USING(product_id);
SELECT (SELECT count(*) FROM gpu_details WHERE gpu_architecture IS NULL) AS gpu_architecture_missing,
       (SELECT count(*) FROM gpu_details WHERE tdp_watts IS NULL) AS gpu_tdp_missing,
       (SELECT count(*) FROM ram_details WHERE speed_mts IS NULL) AS ram_speed_missing,
       (SELECT count(*) FROM ssd_details WHERE nand_type IS NULL) AS ssd_nand_missing,
       (SELECT count(*) FROM ssd_details WHERE tbw IS NULL) AS ssd_tbw_missing,
       (SELECT count(*) FROM price_history WHERE seller_name IS NULL) AS seller_unknown_observations;

\echo '8. GPU RTX/RX families and generations (model text, UNKNOWN explicit)'
SELECT CASE WHEN gd.gpu_model ~* 'RTX' THEN 'RTX'
            WHEN gd.gpu_model ~* 'RX' THEN 'RX' ELSE 'UNKNOWN' END AS gpu_family,
       coalesce((regexp_match(replace(gd.gpu_model,'™',''),'(RTX|RX)[[:space:]]*([0-9]{4})','i'))[2], 'UNKNOWN') AS model_number,
       count(*) AS products
FROM product p JOIN category c USING(category_id)
LEFT JOIN gpu_details gd USING(product_id)
WHERE c.name='GPU' GROUP BY 1,2 ORDER BY 1,2;

\echo '9. RAM types/capacities and SSD PCIe generations/capacities'
SELECT coalesce(rd.ram_type,'UNKNOWN') AS ram_type,
       coalesce(rd.total_capacity_gb::text,'UNKNOWN') AS capacity_gb,
       count(*) AS products
FROM product p JOIN category c USING(category_id)
LEFT JOIN ram_details rd USING(product_id)
WHERE c.name='RAM' GROUP BY 1,2 ORDER BY 1,2;
SELECT coalesce(sd.pcie_generation,'UNKNOWN') AS pcie_generation,
       coalesce(sd.capacity_gb::text,'UNKNOWN') AS capacity_gb,
       count(*) AS products
FROM product p JOIN category c USING(category_id)
LEFT JOIN ssd_details sd USING(product_id)
WHERE c.name='SSD' GROUP BY 1,2 ORDER BY 1,2;

\echo '10. Latest valid offer prices by category'
WITH latest AS (
    SELECT DISTINCT ON (rp.retailer_product_id) c.name AS category, ph.price_chf
    FROM retailer_product rp JOIN product p USING(product_id)
    JOIN category c USING(category_id) JOIN price_history ph USING(retailer_product_id)
    WHERE ph.currency='CHF' AND ph.price_chf>0
    ORDER BY rp.retailer_product_id,ph.collected_at DESC
)
SELECT category,count(*) AS offers,min(price_chf) AS min_chf,
       round(avg(price_chf),2) AS avg_chf,max(price_chf) AS max_chf
FROM latest GROUP BY category ORDER BY category;

\echo '11. Price changes, including same-price new-day observations'
WITH changes AS (
    SELECT rp.retailer_sku,ph.collected_at,ph.price_chf,
           lag(ph.price_chf) OVER (PARTITION BY rp.retailer_product_id ORDER BY ph.collected_at) AS previous_price
    FROM price_history ph JOIN retailer_product rp USING(retailer_product_id)
)
SELECT retailer_sku,count(*) FILTER (WHERE previous_price IS NOT NULL) AS repeat_observations,
       count(*) FILTER (WHERE previous_price IS NOT NULL AND previous_price<>price_chf) AS price_changes,
       count(*) FILTER (WHERE previous_price=price_chf) AS same_price_observations
FROM changes GROUP BY retailer_sku ORDER BY retailer_sku;

\echo '12. Quality: duplicates, invalid price, absent raw reference, raw-import results'
SELECT (SELECT count(*) FROM (
    SELECT retailer_product_id,collected_at FROM price_history GROUP BY 1,2 HAVING count(*)>1) d) AS duplicate_observation_keys,
    count(*) FILTER (WHERE currency<>'CHF' OR price_chf<=0) AS invalid_prices,
    count(*) FILTER (WHERE raw_sha256 IS NULL) AS observations_without_raw_sha
FROM price_history;
SELECT status,coalesce(reason,'') AS reason,count(*) AS raw_files
FROM raw_import GROUP BY 1,2 ORDER BY 1,2;
