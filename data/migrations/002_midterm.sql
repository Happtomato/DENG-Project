-- Small additive extension of the original nine-table schema.
-- Existing rows are never deleted or silently corrected.
CREATE UNIQUE INDEX uq_product_gtin ON product (lpad(ean,14,'0')) WHERE ean IS NOT NULL;
CREATE UNIQUE INDEX uq_product_brand_mpn ON product (brand_id,upper(btrim(mpn))) WHERE mpn IS NOT NULL;
CREATE UNIQUE INDEX uq_brand_normalized ON brand (lower(btrim(name)));

CREATE TABLE raw_import (
    sha256 TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    evidence_path TEXT,
    status TEXT NOT NULL CHECK (status IN ('loaded','duplicate','rejected','error')),
    reason TEXT,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- collected_at already stores the source observation time. Keep that meaning.
ALTER TABLE price_history
    ADD COLUMN raw_sha256 TEXT REFERENCES raw_import(sha256),
    ADD COLUMN source_url TEXT,
    ADD COLUMN ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN currency TEXT NOT NULL DEFAULT 'CHF' CHECK (currency='CHF'),
    ADD COLUMN seller_name TEXT;
ALTER TABLE price_history ADD CONSTRAINT chk_midterm_price CHECK (price_chf>0) NOT VALID;
ALTER TABLE retailer_product ADD CONSTRAINT chk_midterm_sku CHECK (retailer_sku IS NOT NULL AND btrim(retailer_sku)<>'') NOT VALID;

CREATE VIEW hardware_prices AS
SELECT p.product_id, p.product_name, c.name AS category, b.name AS manufacturer,
       p.ean, p.mpn, r.name AS platform, rp.retailer_sku,
       ph.seller_name, ph.price_chf, ph.currency, ph.availability,
       ph.collected_at AS observed_at,
       (ph.collected_at AT TIME ZONE 'Europe/Zurich')::date AS observation_date,
       ph.ingested_at, ph.source_url, ri.path AS raw_path,
       sd.capacity_gb AS ssd_capacity_gb,
       CASE WHEN sd.capacity_gb>0 THEN round(ph.price_chf/sd.capacity_gb,4) END AS ssd_chf_per_gb
FROM price_history ph
JOIN retailer_product rp USING(retailer_product_id)
JOIN product p USING(product_id)
JOIN category c USING(category_id)
JOIN brand b USING(brand_id)
JOIN retailer r USING(retailer_id)
LEFT JOIN raw_import ri ON ri.sha256=ph.raw_sha256
LEFT JOIN ssd_details sd USING(product_id);
