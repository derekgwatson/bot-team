-- Mavis Unleashed Integration Database Schema
-- Stores synced Unleashed product data for other bots to query

-- Products table - stores Unleashed product data
CREATE TABLE IF NOT EXISTS unleashed_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Product identification (normalized)
    product_code TEXT NOT NULL UNIQUE,

    -- Product details
    product_description TEXT,
    product_group TEXT,

    -- Pricing
    default_sell_price REAL,
    sell_price_tier_9 REAL,

    -- Product attributes
    unit_of_measure TEXT,
    width REAL,

    -- Raw data storage for debugging/future use
    raw_payload TEXT,  -- JSON string of full Unleashed product

    -- Audit fields (UTC ISO8601)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Sync metadata table - tracks sync operations
CREATE TABLE IF NOT EXISTS sync_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Sync identification
    sync_type TEXT NOT NULL,  -- 'products', 'customers', 'orders' etc.

    -- Sync results
    status TEXT NOT NULL,  -- 'success', 'failed'
    records_processed INTEGER DEFAULT 0,
    records_created INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,

    -- Timing
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_seconds REAL,

    -- Error tracking
    error_message TEXT
);

-- Indexes for quick lookups
CREATE INDEX IF NOT EXISTS idx_products_code ON unleashed_products(product_code);
CREATE INDEX IF NOT EXISTS idx_products_group ON unleashed_products(product_group);
CREATE INDEX IF NOT EXISTS idx_products_updated ON unleashed_products(updated_at);
CREATE INDEX IF NOT EXISTS idx_sync_type ON sync_metadata(sync_type);
CREATE INDEX IF NOT EXISTS idx_sync_started ON sync_metadata(started_at);
