-- Keep captured offers for reproducibility even when they are not monitored daily.
-- Existing offers remain active; only explicitly reviewed captures are deactivated.
ALTER TABLE retailer_product
    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN tracking_reason TEXT;
