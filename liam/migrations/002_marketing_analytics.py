"""
Migration for marketing analytics features.

Adds tables for:
- daily_lead_counts: Historical daily lead data for trend analysis
- marketing_events: Campaign dates and marketing activities
"""


def up(conn):
    """Create marketing analytics tables."""

    # Table for storing daily lead counts
    conn.execute('''
        CREATE TABLE IF NOT EXISTS daily_lead_counts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_key TEXT NOT NULL,
            date TEXT NOT NULL,
            lead_count INTEGER NOT NULL DEFAULT 0,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(org_key, date)
        )
    ''')

    # Indexes for efficient querying
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_daily_leads_org_date
        ON daily_lead_counts(org_key, date DESC)
    ''')

    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_daily_leads_date
        ON daily_lead_counts(date DESC)
    ''')

    # Table for marketing events/campaigns
    conn.execute('''
        CREATE TABLE IF NOT EXISTS marketing_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            event_type TEXT NOT NULL DEFAULT 'campaign',
            start_date TEXT NOT NULL,
            end_date TEXT,
            target_orgs TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT DEFAULT NULL
        )
    ''')

    # Index for querying events by date range
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_marketing_events_dates
        ON marketing_events(start_date, end_date)
    ''')


def down(conn):
    """Drop marketing analytics tables."""
    conn.execute('DROP TABLE IF EXISTS daily_lead_counts')
    conn.execute('DROP TABLE IF EXISTS marketing_events')
