# Database Migrations Framework

A simple, reusable database migrations system for all bots in the bot-team project.

## Features

- **Version Tracking**: Tracks which migrations have been applied using a `migrations` table
- **Auto-run**: Migrations run automatically on application startup
- **Idempotent**: Safe to run multiple times - only pending migrations are applied
- **Simple**: Just Python files with `up()` and `down()` functions
- **Shared**: Common framework used across all bots

## Usage

### 1. In Your Bot's Database Class

```python
import sys
from pathlib import Path
from contextlib import contextmanager
import sqlite3

# Add shared directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.migrations import MigrationRunner


class Database:
    def __init__(self, db_path: str = None, auto_migrate: bool = True):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'bot.db'

        self.db_path = db_path
        self.migrations_dir = Path(__file__).parent.parent / 'migrations'

        if auto_migrate:
            self.run_migrations()

    def run_migrations(self, verbose: bool = False):
        """Run database migrations."""
        runner = MigrationRunner(
            db_path=str(self.db_path),
            migrations_dir=str(self.migrations_dir)
        )
        runner.run_pending_migrations(verbose=verbose)
```

### 2. Create Your Bot's Migrations Directory

```bash
mkdir your-bot/migrations
```

### 3. Create Migration Files

Migration files should be named with a version number prefix: `001_description.py`, `002_add_users.py`, etc.

**Example: `001_initial_schema.py`**

```python
"""Initial database schema."""

def up(conn):
    """Create initial tables."""
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')


def down(conn):
    """Drop all tables."""
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS users')
    cursor.execute('DROP TABLE IF EXISTS settings')
```

**Example: `002_seed_data.py`**

```python
"""Seed initial data."""

def up(conn):
    """Insert initial settings."""
    cursor = conn.cursor()

    settings = [
        ('app_name', 'My Bot'),
        ('version', '1.0.0'),
    ]

    cursor.executemany(
        'INSERT INTO settings (key, value) VALUES (?, ?)',
        settings
    )


def down(conn):
    """Remove seeded data."""
    cursor = conn.cursor()
    cursor.execute('DELETE FROM settings')
```

### 4. Migrations Run Automatically

When your bot starts, migrations run automatically:

```python
from services.database import db  # Migrations run here!
```

## Migration File Rules

1. **Naming**: `{version}_{description}.py` (e.g., `001_initial.py`, `002_add_users.py`)
2. **Version**: Sequential numbers (001, 002, 003, etc.)
3. **Required**: Each file must have an `up(conn)` function
4. **Optional**: `down(conn)` function for rollbacks
5. **Parameters**: Both functions receive a SQLite connection object

## How It Works

1. On first run, creates a `migrations` table to track applied migrations
2. Scans the migrations directory for `*.py` files
3. Checks which migrations haven't been applied yet
4. Runs pending migrations in version order
5. Records each migration in the `migrations` table after successful application

## Migrations Table Schema

```sql
CREATE TABLE migrations (
    version TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## Manual Migration Management

If you need to manually run or check migrations:

```python
from shared.migrations import MigrationRunner

runner = MigrationRunner(
    db_path='path/to/bot.db',
    migrations_dir='path/to/migrations'
)

# Run pending migrations with output
runner.run_pending_migrations(verbose=True)

# Check migration status
status = runner.get_status()
print(f"Applied: {status['total_applied']}")
print(f"Pending: {status['total_pending']}")

# Rollback last migration (if down() is implemented)
runner.rollback_last(verbose=True)
```

## Example: Chester's Migrations

See `/home/user/bot-team/chester/migrations/` for a working example:

- `001_initial_schema.py` - Creates tables and default config
- `002_seed_bots.py` - Seeds initial bot data

## Best Practices

1. **Never modify applied migrations** - Create a new migration instead
2. **Keep migrations small** - One logical change per migration
3. **Test rollbacks** - Implement `down()` and test it works
4. **Descriptive names** - Use clear, meaningful migration names
5. **Version control** - Commit migrations with your code

## Benefits

- ✅ Consistent migration pattern across all bots
- ✅ Automatic database setup on first run
- ✅ Safe schema changes in production
- ✅ Migration history tracking
- ✅ Easy rollback capability
- ✅ No manual SQL script running

## Future Enhancements

Potential additions:
- Transaction support for complex migrations
- Migration dependencies/prerequisites
- Data validation before/after migrations
- Migration dry-run mode
- CLI tool for migration management
