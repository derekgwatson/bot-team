"""
Initial schema for Doc database

Tables:
- bots: Bot registry (synced from Chester)
- checkups: Health check results
- test_runs: Test execution history
"""


def up(conn):
    cursor = conn.cursor()

    # Bot registry - synced from Chester but stored locally
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            port INTEGER NOT NULL,
            url TEXT NOT NULL,
            description TEXT,
            capabilities TEXT,  -- JSON array
            last_synced_at TIMESTAMP
        )
    ''')

    # Health checkup results
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checkups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_name TEXT NOT NULL,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,  -- healthy, unhealthy, unreachable, timeout, error
            response_time_ms INTEGER,
            status_code INTEGER,
            error_message TEXT
        )
    ''')

    # Index for faster lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_checkups_bot_time
        ON checkups(bot_name, checked_at DESC)
    ''')

    # Test run history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            marker TEXT,  -- pytest marker (e.g., 'fred', 'integration', 'unit', or null for all)
            status TEXT NOT NULL,  -- running, passed, failed, error
            total_tests INTEGER DEFAULT 0,
            passed INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0,
            duration_seconds REAL,
            output TEXT,  -- Full pytest output (truncated if too long)
            error_message TEXT
        )
    ''')

    # Index for test run lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_test_runs_marker_time
        ON test_runs(marker, started_at DESC)
    ''')


def down(conn):
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS test_runs')
    cursor.execute('DROP TABLE IF EXISTS checkups')
    cursor.execute('DROP TABLE IF EXISTS bots')
