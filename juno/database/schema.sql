-- Juno (Customer Tracking Experience) Database Schema
-- SQLite database for managing tracking links and customer sessions

-- Tracking links table: unique links sent to customers
CREATE TABLE IF NOT EXISTS tracking_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,              -- Unique tracking code (e.g., "abc123xyz789")
    journey_id INTEGER NOT NULL,            -- Travis journey ID
    staff_id INTEGER NOT NULL,              -- Travis staff ID
    customer_name TEXT,                     -- Customer name for display
    customer_phone TEXT,                    -- Customer phone (for SMS links)
    customer_email TEXT,                    -- Customer email (for email links)
    destination_address TEXT,               -- Delivery/visit address
    destination_lat REAL,                   -- Destination latitude
    destination_lng REAL,                   -- Destination longitude
    status TEXT DEFAULT 'active',           -- active, arrived, expired, cancelled
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,           -- When link becomes invalid
    first_viewed_at DATETIME,               -- When customer first opened link
    view_count INTEGER DEFAULT 0,           -- Number of times link was viewed
    arrived_at DATETIME,                    -- When staff arrived
    completed_at DATETIME                   -- When tracking session ended
);

-- Tracking events table: log of events for analytics
CREATE TABLE IF NOT EXISTS tracking_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_link_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,               -- created, viewed, location_update, arrived, expired
    event_data TEXT,                        -- JSON data for the event
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tracking_link_id) REFERENCES tracking_links(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_links_code ON tracking_links(code);
CREATE INDEX IF NOT EXISTS idx_links_journey_id ON tracking_links(journey_id);
CREATE INDEX IF NOT EXISTS idx_links_staff_id ON tracking_links(staff_id);
CREATE INDEX IF NOT EXISTS idx_links_status ON tracking_links(status);
CREATE INDEX IF NOT EXISTS idx_links_expires_at ON tracking_links(expires_at);

CREATE INDEX IF NOT EXISTS idx_events_link_id ON tracking_events(tracking_link_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON tracking_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON tracking_events(created_at);
