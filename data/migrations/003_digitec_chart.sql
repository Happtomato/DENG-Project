-- Digitec chart change points are not daily observations in price_history.
-- Keep the source's validFrom and nullable price without inventing measurements.
CREATE TABLE retailer_price_change (
    retailer_product_id BIGINT NOT NULL REFERENCES retailer_product(retailer_product_id),
    valid_from TIMESTAMPTZ NOT NULL,
    price_chf NUMERIC(12,2),
    point_type TEXT NOT NULL CHECK (point_type IN ('price','no_price')),
    raw_sha256 TEXT NOT NULL REFERENCES raw_import(sha256),
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (retailer_product_id,valid_from),
    CONSTRAINT chk_chart_point_value CHECK (
        (point_type='price' AND price_chf>0) OR
        (point_type='no_price' AND price_chf IS NULL)
    )
);
