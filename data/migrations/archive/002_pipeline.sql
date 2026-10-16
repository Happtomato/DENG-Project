-- Additive migration: keep existing products and observations. No guessed provenance.
ALTER TABLE product ADD COLUMN master_source TEXT;
ALTER TABLE product ADD COLUMN master_status TEXT NOT NULL DEFAULT 'provisional'
    CHECK (master_status IN ('provisional', 'digitec_validated'));
ALTER TABLE product ADD COLUMN mpn_normalized TEXT;
UPDATE product SET mpn_normalized = NULLIF(upper(btrim(mpn)), '');
CREATE UNIQUE INDEX uq_product_brand_mpn ON product (brand_id, mpn_normalized)
    WHERE mpn_normalized IS NOT NULL;
CREATE UNIQUE INDEX uq_brand_name_normalized ON brand (lower(btrim(name)));

CREATE TABLE raw_record (
    raw_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    retailer_code TEXT NOT NULL,
    path TEXT NOT NULL,
    source_url TEXT,
    collected_at TIMESTAMPTZ,
    parser_version TEXT,
    provenance JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','ingested','review','excluded','error')),
    reason TEXT,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE product_gtin (
    gtin14 CHAR(14) PRIMARY KEY CHECK(gtin14 ~ '^[0-9]{14}$'),
    product_id BIGINT NOT NULL REFERENCES product(product_id) ON DELETE RESTRICT,
    raw_record_id BIGINT NOT NULL REFERENCES raw_record(raw_record_id)
);
CREATE INDEX idx_product_gtin_product ON product_gtin(product_id);
CREATE TABLE product_attribute_source (
    product_id BIGINT NOT NULL REFERENCES product(product_id) ON DELETE RESTRICT,
    attribute TEXT NOT NULL,
    value JSONB NOT NULL,
    raw_record_id BIGINT NOT NULL REFERENCES raw_record(raw_record_id),
    PRIMARY KEY(product_id, attribute)
);
CREATE TABLE matching_review (
    raw_record_id BIGINT PRIMARY KEY REFERENCES raw_record(raw_record_id),
    reason TEXT NOT NULL,
    candidate_product_ids BIGINT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE retailer_product ADD COLUMN match_method TEXT;
ALTER TABLE retailer_product ADD COLUMN matched_raw_record_id BIGINT REFERENCES raw_record(raw_record_id);
-- New ingest requires a SKU; retain legacy nulls for explicit review instead of inventing one.
ALTER TABLE retailer_product ADD CONSTRAINT chk_nonempty_sku CHECK(retailer_sku IS NULL OR btrim(retailer_sku) <> '');
ALTER TABLE retailer_product ALTER COLUMN retailer_sku SET NOT NULL;
ALTER TABLE retailer_product DROP CONSTRAINT fk_retailer_product_product;
ALTER TABLE retailer_product ADD CONSTRAINT fk_retailer_product_product
    FOREIGN KEY(product_id) REFERENCES product(product_id) ON DELETE RESTRICT;
ALTER TABLE retailer_product DROP CONSTRAINT fk_retailer_product_retailer;
ALTER TABLE retailer_product ADD CONSTRAINT fk_retailer_product_retailer
    FOREIGN KEY(retailer_id) REFERENCES retailer(retailer_id) ON DELETE RESTRICT;
ALTER TABLE price_history DROP CONSTRAINT fk_price_history_retailer_product;
ALTER TABLE price_history ADD CONSTRAINT fk_price_history_retailer_product
    FOREIGN KEY(retailer_product_id) REFERENCES retailer_product(retailer_product_id) ON DELETE RESTRICT;

-- collected_at means retrieval time. Historical price_date is independent of import time.
ALTER TABLE price_history ADD COLUMN observation_key TEXT;
ALTER TABLE price_history ADD COLUMN observation_type TEXT CHECK(observation_type IN ('daily_scrape','historical_import'));
ALTER TABLE price_history ADD COLUMN observed_at TIMESTAMPTZ;
ALTER TABLE price_history ADD COLUMN price_date DATE;
ALTER TABLE price_history ADD COLUMN time_precision TEXT CHECK(time_precision IN ('timestamp','day'));
ALTER TABLE price_history ADD COLUMN price_basis TEXT;
ALTER TABLE price_history ADD COLUMN currency CHAR(3) CHECK(currency = 'CHF');
ALTER TABLE price_history ADD COLUMN raw_record_id BIGINT REFERENCES raw_record(raw_record_id);
ALTER TABLE price_history ADD COLUMN ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE price_history ADD COLUMN seller_key TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE price_history ADD COLUMN seller_name TEXT;
ALTER TABLE price_history ADD COLUMN seller_is_retailer BOOLEAN;
ALTER TABLE price_history ADD COLUMN original_price_type TEXT;
ALTER TABLE price_history DROP CONSTRAINT uq_price_observation;
ALTER TABLE price_history ADD CONSTRAINT uq_price_observation_key UNIQUE(observation_key);
-- NOT VALID keeps pre-existing problematic rows visible; every new row is checked.
ALTER TABLE price_history ADD CONSTRAINT chk_positive_observation CHECK(price_chf > 0) NOT VALID;
ALTER TABLE price_history ADD CONSTRAINT chk_observation_metadata CHECK (
    observation_key IS NOT NULL AND observation_type IS NOT NULL AND price_date IS NOT NULL
    AND time_precision IS NOT NULL AND price_basis IS NOT NULL AND currency IS NOT NULL
    AND raw_record_id IS NOT NULL
    AND (time_precision <> 'timestamp' OR observed_at IS NOT NULL)
) NOT VALID;
CREATE INDEX idx_price_history_date ON price_history(price_date, retailer_product_id);
ALTER TABLE ram_details ADD CONSTRAINT chk_ram_kit CHECK (
    total_capacity_gb IS NULL OR module_count IS NULL OR capacity_per_module_gb IS NULL
    OR total_capacity_gb = module_count * capacity_per_module_gb
) NOT VALID;

-- Preserve source + seller + day; choose the latest actual scrape, never fill missing days.
CREATE VIEW daily_price_observation AS
SELECT DISTINCT ON (rp.product_id, rp.retailer_id, ph.seller_key, ph.price_date)
    rp.product_id, rp.retailer_id, r.name AS retailer, rp.retailer_sku, rp.product_url,
    ph.seller_key, ph.seller_name, ph.seller_is_retailer,
    ph.price_date, ph.price_chf, ph.observed_at, ph.availability, ph.raw_record_id
FROM price_history ph
JOIN retailer_product rp USING(retailer_product_id)
JOIN retailer r USING(retailer_id)
WHERE ph.observation_type = 'daily_scrape' AND ph.price_basis = 'observed_offer'
ORDER BY rp.product_id, rp.retailer_id, ph.seller_key, ph.price_date,
         ph.observed_at DESC, ph.price_id DESC;

-- Strict own-retailer comparison. Unknown/marketplace sellers remain queryable above.
CREATE VIEW digitec_mediamarkt_comparison AS
SELECT p.product_id, p.product_name, p.master_status, d.price_date,
       d.price_chf AS digitec_chf, m.price_chf AS mediamarkt_chf,
       m.price_chf - d.price_chf AS difference_chf,
       round((m.price_chf - d.price_chf) / d.price_chf * 100, 2) AS difference_percent,
       d.observed_at AS digitec_observed_at, m.observed_at AS mediamarkt_observed_at,
       d.raw_record_id AS digitec_raw_record_id, m.raw_record_id AS mediamarkt_raw_record_id
FROM product p
JOIN daily_price_observation d ON d.product_id = p.product_id AND d.retailer = 'Digitec'
JOIN daily_price_observation m ON m.product_id = p.product_id AND m.retailer = 'MediaMarkt'
                             AND m.price_date = d.price_date
WHERE d.seller_is_retailer IS TRUE AND m.seller_is_retailer IS TRUE;
