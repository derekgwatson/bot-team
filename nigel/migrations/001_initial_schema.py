"""Initial database schema for Nigel's price monitoring."""


def up(conn):
    """Create initial tables."""
    cursor = conn.cursor()

    # Monitored quotes table - quotes Nigel is watching
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monitored_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Quote identification
            quote_id TEXT NOT NULL UNIQUE,
            org TEXT NOT NULL,

            -- Last known price (stored as text to preserve decimal precision)
            last_known_price TEXT DEFAULT NULL,

            -- Tracking
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_checked_at TIMESTAMP DEFAULT NULL,
            price_updated_at TIMESTAMP DEFAULT NULL,

            -- Status
            is_active BOOLEAN DEFAULT 1,
            notes TEXT DEFAULT ''
        )
    ''')

    # Price check history - log of all price checks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Which quote was checked
            quote_id TEXT NOT NULL,
            org TEXT NOT NULL,

            -- Price information
            price_before TEXT DEFAULT NULL,
            price_after TEXT DEFAULT NULL,

            -- Check result
            status TEXT NOT NULL,  -- 'success', 'error', 'timeout'
            has_discrepancy BOOLEAN DEFAULT 0,
            discrepancy_amount TEXT DEFAULT NULL,

            -- Error information
            error_message TEXT DEFAULT NULL,

            -- Timing
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Response data from Banji (stored as JSON)
            banji_response TEXT DEFAULT NULL
        )
    ''')

    # Discrepancies - record of detected price changes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS discrepancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Quote information
            quote_id TEXT NOT NULL,
            org TEXT NOT NULL,

            -- Price information
            expected_price TEXT NOT NULL,
            actual_price TEXT NOT NULL,
            difference TEXT NOT NULL,

            -- Tracking
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Notification status
            notification_status TEXT DEFAULT 'pending',  -- 'pending', 'notified', 'ignored'
            notification_method TEXT DEFAULT NULL,  -- 'ticket', 'email', etc.
            notification_id TEXT DEFAULT NULL,  -- ticket ID, email ID, etc.
            notified_at TIMESTAMP DEFAULT NULL,

            -- Resolution
            resolved BOOLEAN DEFAULT 0,
            resolved_at TIMESTAMP DEFAULT NULL,
            resolved_by TEXT DEFAULT NULL,
            resolution_notes TEXT DEFAULT NULL
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_monitored_quotes_quote_id ON monitored_quotes(quote_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_monitored_quotes_active ON monitored_quotes(is_active)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_checks_quote_id ON price_checks(quote_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_checks_checked_at ON price_checks(checked_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_checks_discrepancy ON price_checks(has_discrepancy)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_discrepancies_quote_id ON discrepancies(quote_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_discrepancies_resolved ON discrepancies(resolved)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_discrepancies_status ON discrepancies(notification_status)')


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS discrepancies')
    cursor.execute('DROP TABLE IF EXISTS price_checks')
    cursor.execute('DROP TABLE IF EXISTS monitored_quotes')
