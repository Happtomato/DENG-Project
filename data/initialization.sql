-- PostgreSQL schema for PC component price tracking
-- Initial database setup

BEGIN;


-- ==========================================
-- BRAND
-- ==========================================

CREATE TABLE IF NOT EXISTS brand (
    brand_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE
);


-- ==========================================
-- CATEGORY
-- ==========================================

CREATE TABLE IF NOT EXISTS category (
    category_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);


-- ==========================================
-- RETAILER
-- ==========================================

CREATE TABLE IF NOT EXISTS retailer (
    retailer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    website TEXT
);


-- ==========================================
-- PRODUCT
-- ==========================================

CREATE TABLE IF NOT EXISTS product (
    product_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    brand_id BIGINT NOT NULL,
    category_id BIGINT NOT NULL,

    product_name TEXT NOT NULL,
    ean VARCHAR(32),
    mpn VARCHAR(255),

    release_date DATE,
    model VARCHAR(255),
    series VARCHAR(255),
    generation VARCHAR(255),

    msrp_chf NUMERIC(12, 2),
    manufacturer_url TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_product_brand
        FOREIGN KEY (brand_id)
        REFERENCES brand (brand_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_product_category
        FOREIGN KEY (category_id)
        REFERENCES category (category_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT chk_product_msrp
        CHECK (
            msrp_chf IS NULL
            OR msrp_chf >= 0
        )
);


-- ==========================================
-- RETAILER PRODUCT
-- ==========================================

CREATE TABLE IF NOT EXISTS retailer_product (
    retailer_product_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    product_id BIGINT NOT NULL,
    retailer_id BIGINT NOT NULL,

    retailer_sku VARCHAR(255),
    retailer_product_name TEXT NOT NULL,
    product_url TEXT,

    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_retailer_product_product
        FOREIGN KEY (product_id)
        REFERENCES product (product_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT fk_retailer_product_retailer
        FOREIGN KEY (retailer_id)
        REFERENCES retailer (retailer_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT uq_retailer_product
        UNIQUE (retailer_id, retailer_sku),

    CONSTRAINT chk_retailer_product_seen_dates
        CHECK (
            last_seen_at >= first_seen_at
        )
);


-- ==========================================
-- PRICE HISTORY
-- ==========================================

CREATE TABLE IF NOT EXISTS price_history (
    price_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    retailer_product_id BIGINT NOT NULL,

    price_chf NUMERIC(12, 2) NOT NULL,
    original_price_chf NUMERIC(12, 2),
    discount_percent NUMERIC(5, 2),

    availability VARCHAR(255),

    collected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_price_history_retailer_product
        FOREIGN KEY (retailer_product_id)
        REFERENCES retailer_product (retailer_product_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT chk_price_history_price
        CHECK (
            price_chf >= 0
        ),

    CONSTRAINT chk_price_history_original_price
        CHECK (
            original_price_chf IS NULL
            OR original_price_chf >= 0
        ),

    CONSTRAINT chk_price_history_discount
        CHECK (
            discount_percent IS NULL
            OR (
                discount_percent >= 0
                AND discount_percent <= 100
            )
        ),

    CONSTRAINT uq_price_observation
        UNIQUE (
            retailer_product_id,
            collected_at
        )
);


-- ==========================================
-- GPU DETAILS
-- ==========================================

CREATE TABLE IF NOT EXISTS gpu_details (
    gpu_details_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    product_id BIGINT NOT NULL UNIQUE,

    gpu_model VARCHAR(255),
    gpu_architecture VARCHAR(255),

    vram_gb INTEGER,
    vram_type VARCHAR(100),

    clock_mhz INTEGER,
    boost_clock_mhz INTEGER,

    pcie_interface VARCHAR(100),
    tdp_watts INTEGER,
    cooling_variant VARCHAR(255),

    CONSTRAINT fk_gpu_details_product
        FOREIGN KEY (product_id)
        REFERENCES product (product_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT chk_gpu_vram
        CHECK (
            vram_gb IS NULL
            OR vram_gb > 0
        ),

    CONSTRAINT chk_gpu_clock
        CHECK (
            clock_mhz IS NULL
            OR clock_mhz > 0
        ),

    CONSTRAINT chk_gpu_boost_clock
        CHECK (
            boost_clock_mhz IS NULL
            OR boost_clock_mhz > 0
        ),

    CONSTRAINT chk_gpu_tdp
        CHECK (
            tdp_watts IS NULL
            OR tdp_watts > 0
        )
);


-- ==========================================
-- RAM DETAILS
-- ==========================================

CREATE TABLE IF NOT EXISTS ram_details (
    ram_details_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    product_id BIGINT NOT NULL UNIQUE,

    ram_type VARCHAR(100),

    total_capacity_gb INTEGER,
    module_count INTEGER,
    capacity_per_module_gb INTEGER,

    speed_mts INTEGER,
    cas_latency VARCHAR(50),
    voltage NUMERIC(5, 2),

    ecc BOOLEAN,
    rgb BOOLEAN,

    CONSTRAINT fk_ram_details_product
        FOREIGN KEY (product_id)
        REFERENCES product (product_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT chk_ram_total_capacity
        CHECK (
            total_capacity_gb IS NULL
            OR total_capacity_gb > 0
        ),

    CONSTRAINT chk_ram_module_count
        CHECK (
            module_count IS NULL
            OR module_count > 0
        ),

    CONSTRAINT chk_ram_module_capacity
        CHECK (
            capacity_per_module_gb IS NULL
            OR capacity_per_module_gb > 0
        ),

    CONSTRAINT chk_ram_speed
        CHECK (
            speed_mts IS NULL
            OR speed_mts > 0
        ),

    CONSTRAINT chk_ram_voltage
        CHECK (
            voltage IS NULL
            OR voltage > 0
        )
);


-- ==========================================
-- SSD DETAILS
-- ==========================================

CREATE TABLE IF NOT EXISTS ssd_details (
    ssd_details_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    product_id BIGINT NOT NULL UNIQUE,

    capacity_gb INTEGER,

    interface VARCHAR(100),
    pcie_generation VARCHAR(100),
    form_factor VARCHAR(100),

    nand_type VARCHAR(100),
    controller VARCHAR(255),

    read_speed_mbps INTEGER,
    write_speed_mbps INTEGER,

    tbw INTEGER,
    dram_cache BOOLEAN,

    CONSTRAINT fk_ssd_details_product
        FOREIGN KEY (product_id)
        REFERENCES product (product_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT chk_ssd_capacity
        CHECK (
            capacity_gb IS NULL
            OR capacity_gb > 0
        ),

    CONSTRAINT chk_ssd_read_speed
        CHECK (
            read_speed_mbps IS NULL
            OR read_speed_mbps > 0
        ),

    CONSTRAINT chk_ssd_write_speed
        CHECK (
            write_speed_mbps IS NULL
            OR write_speed_mbps > 0
        ),

    CONSTRAINT chk_ssd_tbw
        CHECK (
            tbw IS NULL
            OR tbw >= 0
        )
);


-- ==========================================
-- INDEXES
-- ==========================================

CREATE INDEX IF NOT EXISTS idx_product_brand_id
    ON product (brand_id);

CREATE INDEX IF NOT EXISTS idx_product_category_id
    ON product (category_id);

CREATE INDEX IF NOT EXISTS idx_product_ean
    ON product (ean);

CREATE INDEX IF NOT EXISTS idx_product_mpn
    ON product (mpn);

CREATE INDEX IF NOT EXISTS idx_retailer_product_product_id
    ON retailer_product (product_id);

CREATE INDEX IF NOT EXISTS idx_retailer_product_retailer_id
    ON retailer_product (retailer_id);

CREATE INDEX IF NOT EXISTS idx_price_history_retailer_product_collected
    ON price_history (
        retailer_product_id,
        collected_at DESC
    );

CREATE INDEX IF NOT EXISTS idx_price_history_collected_at
    ON price_history (
        collected_at DESC
    );


COMMIT;