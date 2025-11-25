-- Oscar's Onboarding Database Schema
-- Tracks staff onboarding workflows and manual tasks

-- Onboarding requests table
CREATE TABLE IF NOT EXISTS onboarding_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Staff Information
    full_name TEXT NOT NULL,
    preferred_name TEXT DEFAULT '',
    position TEXT NOT NULL,
    section TEXT NOT NULL,
    start_date DATE NOT NULL,

    -- Contact Information
    personal_email TEXT NOT NULL,
    phone_mobile TEXT DEFAULT '',
    phone_fixed TEXT DEFAULT '',

    -- System Access Requirements
    google_access BOOLEAN DEFAULT 1,
    zendesk_access BOOLEAN DEFAULT 0,
    voip_access BOOLEAN DEFAULT 0,

    -- Work email (stored when creating request, used when executing Google step)
    work_email TEXT DEFAULT NULL,

    -- Zendesk configuration
    zendesk_groups TEXT DEFAULT NULL,  -- JSON array of group IDs to assign

    -- Additional Information
    notes TEXT DEFAULT '',

    -- Workflow Status
    status TEXT DEFAULT 'pending',  -- pending, in_progress, completed, failed

    -- Audit Fields
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_date TIMESTAMP DEFAULT NULL,
    created_by TEXT DEFAULT 'system',

    -- Result tracking
    google_user_email TEXT DEFAULT NULL,
    google_user_password TEXT DEFAULT NULL,
    google_backup_codes TEXT DEFAULT NULL,  -- JSON array of backup codes
    zendesk_user_id TEXT DEFAULT NULL,
    peter_staff_id TEXT DEFAULT NULL,
    error_message TEXT DEFAULT NULL
);

-- Workflow steps table - tracks individual steps in the onboarding process
CREATE TABLE IF NOT EXISTS workflow_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    onboarding_request_id INTEGER NOT NULL,

    -- Step details
    step_name TEXT NOT NULL,  -- 'notify_ian', 'create_google_user', 'create_zendesk_user', 'register_peter', 'voip_ticket'
    step_order INTEGER NOT NULL,

    -- Status
    status TEXT DEFAULT 'pending',  -- pending, in_progress, completed, failed, skipped

    -- Execution details
    started_date TIMESTAMP DEFAULT NULL,
    completed_date TIMESTAMP DEFAULT NULL,

    -- Results
    success BOOLEAN DEFAULT 0,
    result_data TEXT DEFAULT NULL,  -- JSON blob with step-specific results
    error_message TEXT DEFAULT NULL,

    -- Manual task tracking (for VOIP setup)
    requires_manual_action BOOLEAN DEFAULT 0,
    manual_action_instructions TEXT DEFAULT NULL,
    zendesk_ticket_id TEXT DEFAULT NULL,

    FOREIGN KEY (onboarding_request_id) REFERENCES onboarding_requests(id) ON DELETE CASCADE
);

-- Activity log - audit trail of all actions
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    onboarding_request_id INTEGER NOT NULL,

    -- Activity details
    activity_type TEXT NOT NULL,  -- 'request_created', 'step_started', 'step_completed', 'step_failed', etc.
    description TEXT NOT NULL,

    -- Metadata
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system',
    metadata TEXT DEFAULT NULL,  -- JSON blob with additional context

    FOREIGN KEY (onboarding_request_id) REFERENCES onboarding_requests(id) ON DELETE CASCADE
);

-- Indexes for quick lookups
CREATE INDEX IF NOT EXISTS idx_onboarding_status ON onboarding_requests(status);
CREATE INDEX IF NOT EXISTS idx_onboarding_created_date ON onboarding_requests(created_date);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_request ON workflow_steps(onboarding_request_id);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_status ON workflow_steps(status);
CREATE INDEX IF NOT EXISTS idx_activity_log_request ON activity_log(onboarding_request_id);

-- Trigger to update completed_date when status changes to completed
CREATE TRIGGER IF NOT EXISTS update_onboarding_completed_date
AFTER UPDATE OF status ON onboarding_requests
WHEN NEW.status = 'completed'
BEGIN
    UPDATE onboarding_requests SET completed_date = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
