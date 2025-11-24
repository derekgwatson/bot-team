-- Fiona Fabric Descriptions Database Schema
-- Stores friendly names for Unleashed fabric products

-- Fabric descriptions table
-- Maps Unleashed product codes to friendly supplier and Watson names
CREATE TABLE IF NOT EXISTS fabric_descriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Product identification (from Unleashed via Mavis)
    product_code TEXT NOT NULL UNIQUE,

    -- Original supplier names (3 fields)
    supplier_material TEXT,      -- e.g., "Blockout"
    supplier_material_type TEXT, -- e.g., "Roller Blind"
    supplier_colour TEXT,        -- e.g., "Cream"

    -- Watson re-badged names (2 fields - material_type is never changed)
    -- Leave blank if using supplier names
    watson_material TEXT,        -- e.g., "Premium Blackout"
    watson_colour TEXT,          -- e.g., "Ivory"

    -- Audit fields (UTC ISO8601)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT              -- Email of user who last updated
);

-- Indexes for quick lookups
CREATE INDEX IF NOT EXISTS idx_fabric_product_code ON fabric_descriptions(product_code);
CREATE INDEX IF NOT EXISTS idx_fabric_supplier_material ON fabric_descriptions(supplier_material);
CREATE INDEX IF NOT EXISTS idx_fabric_watson_material ON fabric_descriptions(watson_material);
CREATE INDEX IF NOT EXISTS idx_fabric_updated ON fabric_descriptions(updated_at);
