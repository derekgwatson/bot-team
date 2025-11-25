-- Zac's Pending Operations Database Schema
-- Tracks queued operations that can be executed later

CREATE TABLE IF NOT EXISTS pending_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Operation type: create_user, suspend_user, unsuspend_user, delete_user
    operation_type TEXT NOT NULL,

    -- Status: pending, executing, completed, failed, cancelled
    status TEXT DEFAULT 'pending',

    -- Operation data (JSON blob with all details needed to execute)
    operation_data TEXT NOT NULL,

    -- For quick lookups - extracted from operation_data
    target_email TEXT,
    target_name TEXT,
    target_user_id INTEGER,

    -- Execution tracking
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system',
    executed_date TIMESTAMP DEFAULT NULL,
    executed_by TEXT DEFAULT NULL,

    -- Results
    result_data TEXT DEFAULT NULL,  -- JSON blob with result (user ID, etc.)
    error_message TEXT DEFAULT NULL,

    -- Reference ID for external systems (like Oscar's request ID)
    external_reference TEXT DEFAULT NULL
);

-- Indexes for quick lookups
CREATE INDEX IF NOT EXISTS idx_operations_status ON pending_operations(status);
CREATE INDEX IF NOT EXISTS idx_operations_type ON pending_operations(operation_type);
CREATE INDEX IF NOT EXISTS idx_operations_created ON pending_operations(created_date);
CREATE INDEX IF NOT EXISTS idx_operations_email ON pending_operations(target_email);
CREATE INDEX IF NOT EXISTS idx_operations_external_ref ON pending_operations(external_reference);
