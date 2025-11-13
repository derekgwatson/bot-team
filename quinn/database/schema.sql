-- External Staff Database Schema

CREATE TABLE IF NOT EXISTS external_staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    role TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by TEXT,
    modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_email ON external_staff(email);
CREATE INDEX IF NOT EXISTS idx_status ON external_staff(status);

-- Pending Access Requests
CREATE TABLE IF NOT EXISTS pending_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    reason TEXT,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'denied')),
    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_by TEXT,
    reviewed_date TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_request_email ON pending_requests(email);
CREATE INDEX IF NOT EXISTS idx_request_status ON pending_requests(status);
