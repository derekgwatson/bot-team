-- Monica (ChromeOS Monitoring Agent) Database Schema
-- SQLite database for tracking stores, devices, and heartbeats

-- Stores table: retail store locations
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_code TEXT UNIQUE NOT NULL,
    display_name TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Devices table: ChromeOS devices at each store
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER NOT NULL,
    device_label TEXT NOT NULL,
    agent_token TEXT UNIQUE NOT NULL,
    last_heartbeat_at DATETIME,
    last_status TEXT DEFAULT 'offline',
    last_public_ip TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE CASCADE,
    UNIQUE(store_id, device_label)
);

-- Heartbeats table: historical heartbeat data
CREATE TABLE IF NOT EXISTS heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    public_ip TEXT,
    user_agent TEXT,
    latency_ms REAL,
    download_mbps REAL,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

-- Registration codes table: one-time codes for secure device registration
CREATE TABLE IF NOT EXISTS registration_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    store_code TEXT NOT NULL,
    device_label TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    used_at DATETIME,
    used_by_device_id INTEGER,
    expires_at DATETIME,
    FOREIGN KEY (used_by_device_id) REFERENCES devices(id) ON DELETE SET NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_devices_store_id ON devices(store_id);
CREATE INDEX IF NOT EXISTS idx_devices_agent_token ON devices(agent_token);
CREATE INDEX IF NOT EXISTS idx_heartbeats_device_id ON heartbeats(device_id);
CREATE INDEX IF NOT EXISTS idx_heartbeats_timestamp ON heartbeats(timestamp);
CREATE INDEX IF NOT EXISTS idx_heartbeats_device_timestamp ON heartbeats(device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_registration_codes_code ON registration_codes(code);
CREATE INDEX IF NOT EXISTS idx_registration_codes_used_at ON registration_codes(used_at);

-- Trigger to update device updated_at timestamp
CREATE TRIGGER IF NOT EXISTS update_device_timestamp
AFTER UPDATE ON devices
FOR EACH ROW
BEGIN
    UPDATE devices SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
