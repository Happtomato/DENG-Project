SELECT lower(c.name) AS category,rp.retailer_sku AS mediamarkt_sku,
       p.product_name,p.ean
FROM retailer_product rp
JOIN retailer r USING(retailer_id)
JOIN product p USING(product_id)
JOIN category c USING(category_id)
WHERE r.name='MediaMarkt' AND rp.retailer_sku IN
    ('2277758','2277995','2230728','101374309','107353786','2155505','2199070','2155504')
ORDER BY category,mediamarkt_sku;

SELECT r.name AS retailer,rp.retailer_sku,p.product_name,ph.price_chf,ph.collected_at
FROM price_history ph
JOIN retailer_product rp USING(retailer_product_id)
JOIN retailer r USING(retailer_id)
JOIN product p USING(product_id)
WHERE r.name='Digitec'
ORDER BY ph.collected_at DESC;

SELECT r.name AS retailer,rp.retailer_sku,count(*) AS chart_points,
       min(pc.valid_from) AS first_valid_from,max(pc.valid_from) AS last_valid_from,
       count(*) FILTER (WHERE pc.point_type='no_price') AS gaps
FROM retailer_price_change pc
JOIN retailer_product rp USING(retailer_product_id)
JOIN retailer r USING(retailer_id)
WHERE r.name='Digitec'
GROUP BY r.name,rp.retailer_sku ORDER BY rp.retailer_sku;
