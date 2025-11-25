-- Tracker (Field Staff Location Tracking) Database Schema
-- SQLite database for tracking staff locations during customer journeys

-- Staff table: field staff who use the tracking app
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    device_token TEXT UNIQUE,          -- Token for authenticating device pings
    current_status TEXT DEFAULT 'off_duty',  -- off_duty, in_transit, at_customer, on_break
    last_ping_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Journeys table: a journey from current location to customer
CREATE TABLE IF NOT EXISTS journeys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    job_reference TEXT,                -- External reference (e.g., job/appointment ID)
    customer_name TEXT,
    customer_address TEXT,
    customer_lat REAL,                 -- Customer destination latitude
    customer_lng REAL,                 -- Customer destination longitude
    status TEXT DEFAULT 'pending',     -- pending, in_progress, arrived, completed, cancelled
    started_at DATETIME,               -- When staff marked "start journey"
    arrived_at DATETIME,               -- When staff arrived (manual or geofence)
    completed_at DATETIME,             -- When journey fully completed
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE
);

-- Location pings table: GPS coordinates received from devices
CREATE TABLE IF NOT EXISTS location_pings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    journey_id INTEGER,                -- NULL if not on an active journey
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    accuracy REAL,                     -- GPS accuracy in meters
    heading REAL,                      -- Direction of travel (0-360 degrees)
    speed REAL,                        -- Speed in m/s
    altitude REAL,                     -- Altitude in meters
    battery_level REAL,                -- Device battery percentage (0-100)
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE,
    FOREIGN KEY (journey_id) REFERENCES journeys(id) ON DELETE SET NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_staff_email ON staff(email);
CREATE INDEX IF NOT EXISTS idx_staff_device_token ON staff(device_token);
CREATE INDEX IF NOT EXISTS idx_staff_status ON staff(current_status);

CREATE INDEX IF NOT EXISTS idx_journeys_staff_id ON journeys(staff_id);
CREATE INDEX IF NOT EXISTS idx_journeys_status ON journeys(status);
CREATE INDEX IF NOT EXISTS idx_journeys_job_reference ON journeys(job_reference);

CREATE INDEX IF NOT EXISTS idx_pings_staff_id ON location_pings(staff_id);
CREATE INDEX IF NOT EXISTS idx_pings_journey_id ON location_pings(journey_id);
CREATE INDEX IF NOT EXISTS idx_pings_timestamp ON location_pings(timestamp);
CREATE INDEX IF NOT EXISTS idx_pings_staff_timestamp ON location_pings(staff_id, timestamp DESC);

-- Trigger to update staff updated_at timestamp
CREATE TRIGGER IF NOT EXISTS update_staff_timestamp
AFTER UPDATE ON staff
FOR EACH ROW
BEGIN
    UPDATE staff SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
