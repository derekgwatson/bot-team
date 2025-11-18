-- Peter's HR Database Schema
-- Single source of truth for all staff information

CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Basic Information
    name TEXT NOT NULL,
    position TEXT DEFAULT '',
    section TEXT DEFAULT '',

    -- Contact Information
    extension TEXT DEFAULT '',
    phone_fixed TEXT DEFAULT '',
    phone_mobile TEXT DEFAULT '',
    work_email TEXT DEFAULT '',
    personal_email TEXT DEFAULT '',

    -- System Access Flags
    zendesk_access BOOLEAN DEFAULT 0,
    buz_access BOOLEAN DEFAULT 0,
    google_access BOOLEAN DEFAULT 0,
    wiki_access BOOLEAN DEFAULT 0,
    voip_access BOOLEAN DEFAULT 0,

    -- Display Flags
    show_on_phone_list BOOLEAN DEFAULT 1,
    include_in_allstaff BOOLEAN DEFAULT 1,

    -- Status
    status TEXT DEFAULT 'active',  -- active, inactive, onboarding, offboarding, finished
    finish_date DATE,  -- Date when staff member left (set by offboarding process)

    -- Audit Fields
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system',
    modified_by TEXT DEFAULT 'system',

    -- Notes
    notes TEXT DEFAULT ''
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_staff_name ON staff(name);
CREATE INDEX IF NOT EXISTS idx_staff_extension ON staff(extension);
CREATE INDEX IF NOT EXISTS idx_staff_email ON staff(work_email);
CREATE INDEX IF NOT EXISTS idx_staff_status ON staff(status);
CREATE INDEX IF NOT EXISTS idx_staff_phone_list ON staff(show_on_phone_list);
CREATE INDEX IF NOT EXISTS idx_staff_allstaff ON staff(include_in_allstaff);

-- Trigger to update modified_date
CREATE TRIGGER IF NOT EXISTS update_staff_timestamp
AFTER UPDATE ON staff
BEGIN
    UPDATE staff SET modified_date = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Sections table for managing departments/teams
CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_order INTEGER DEFAULT 0,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for section ordering
CREATE INDEX IF NOT EXISTS idx_sections_order ON sections(display_order);
