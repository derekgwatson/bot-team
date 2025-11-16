"""
Shared database migrations framework for bot-team.

This module provides a simple migration system that any bot can use.
Migrations are tracked in a migrations table and run automatically on startup.

Usage:
    from shared.migrations import MigrationRunner

    # In your database class or app startup:
    runner = MigrationRunner(db_path='path/to/bot.db', migrations_dir='path/to/migrations')
    runner.run_pending_migrations()

Migration files:
    - Place migration files in your bot's migrations/ directory
    - Name format: 001_initial_schema.py, 002_add_users_table.py, etc.
    - Each migration must have an up() function that takes a database connection
    - Optional: down() function for rollbacks

Example migration file (001_initial_schema.py):
    def up(conn):
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        ''')

    def down(conn):
        cursor = conn.cursor()
        cursor.execute('DROP TABLE users')
"""

import sqlite3
import os
import importlib.util
from pathlib import Path
from typing import List, Dict, Optional
from contextlib import contextmanager


class Migration:
    """Represents a single database migration."""

    def __init__(self, version: str, name: str, filepath: Path):
        self.version = version
        self.name = name
        self.filepath = filepath
        self.module = None

    def load(self):
        """Load the migration module."""
        spec = importlib.util.spec_from_file_location(f"migration_{self.version}", self.filepath)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def up(self, conn: sqlite3.Connection):
        """Run the migration up."""
        if not self.module:
            self.load()

        if not hasattr(self.module, 'up'):
            raise ValueError(f"Migration {self.name} has no up() function")

        self.module.up(conn)

    def down(self, conn: sqlite3.Connection):
        """Run the migration down (rollback)."""
        if not self.module:
            self.load()

        if not hasattr(self.module, 'down'):
            raise ValueError(f"Migration {self.name} has no down() function")

        self.module.down(conn)


class MigrationRunner:
    """Runs database migrations."""

    def __init__(self, db_path: str, migrations_dir: str):
        """
        Initialize migration runner.

        Args:
            db_path: Path to SQLite database file
            migrations_dir: Directory containing migration files
        """
        self.db_path = db_path
        self.migrations_dir = Path(migrations_dir)

        # Ensure migrations directory exists
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

        # Ensure migrations table exists
        self._init_migrations_table()

    @contextmanager
    def get_connection(self):
        """Get a database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _init_migrations_table(self):
        """Create the migrations tracking table if it doesn't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS migrations (
                    version TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def _get_applied_migrations(self) -> List[str]:
        """Get list of already-applied migration versions."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT version FROM migrations ORDER BY version')
            return [row[0] for row in cursor.fetchall()]

    def _get_available_migrations(self) -> List[Migration]:
        """Get list of available migration files."""
        migrations = []

        # Find all Python files in migrations directory
        for filepath in sorted(self.migrations_dir.glob('*.py')):
            if filepath.name.startswith('_'):
                continue  # Skip __init__.py and other special files

            # Parse filename: 001_initial_schema.py -> version=001, name=initial_schema
            filename = filepath.stem
            parts = filename.split('_', 1)

            if len(parts) != 2:
                print(f"Warning: Skipping migration file {filepath.name} (invalid name format)")
                continue

            version = parts[0]
            name = parts[1]

            migrations.append(Migration(version, name, filepath))

        return sorted(migrations, key=lambda m: m.version)

    def _get_pending_migrations(self) -> List[Migration]:
        """Get list of migrations that haven't been applied yet."""
        applied = set(self._get_applied_migrations())
        available = self._get_available_migrations()

        return [m for m in available if m.version not in applied]

    def run_pending_migrations(self, verbose: bool = True) -> int:
        """
        Run all pending migrations.

        Args:
            verbose: If True, print migration status

        Returns:
            Number of migrations applied
        """
        pending = self._get_pending_migrations()

        if not pending:
            if verbose:
                print("No pending migrations.")
            return 0

        if verbose:
            print(f"Running {len(pending)} pending migration(s)...")

        count = 0
        for migration in pending:
            if verbose:
                print(f"  Applying {migration.version}_{migration.name}...", end=" ")

            try:
                with self.get_connection() as conn:
                    # Run the migration
                    migration.up(conn)

                    # Record it in migrations table
                    cursor = conn.cursor()
                    cursor.execute(
                        'INSERT INTO migrations (version, name) VALUES (?, ?)',
                        (migration.version, migration.name)
                    )

                if verbose:
                    print("✓")

                count += 1

            except Exception as e:
                if verbose:
                    print(f"✗ FAILED: {e}")
                raise

        if verbose:
            print(f"Successfully applied {count} migration(s).")

        return count

    def rollback_last(self, verbose: bool = True) -> bool:
        """
        Rollback the last applied migration.

        Args:
            verbose: If True, print rollback status

        Returns:
            True if rollback successful, False if no migrations to rollback
        """
        applied = self._get_applied_migrations()

        if not applied:
            if verbose:
                print("No migrations to rollback.")
            return False

        last_version = applied[-1]

        # Find the migration file
        available = self._get_available_migrations()
        migration = next((m for m in available if m.version == last_version), None)

        if not migration:
            raise ValueError(f"Migration file for version {last_version} not found")

        if verbose:
            print(f"Rolling back {migration.version}_{migration.name}...", end=" ")

        try:
            with self.get_connection() as conn:
                # Run the down migration
                migration.down(conn)

                # Remove from migrations table
                cursor = conn.cursor()
                cursor.execute('DELETE FROM migrations WHERE version = ?', (migration.version,))

            if verbose:
                print("✓")

            return True

        except Exception as e:
            if verbose:
                print(f"✗ FAILED: {e}")
            raise

    def get_status(self) -> Dict:
        """Get migration status information."""
        applied = self._get_applied_migrations()
        available = self._get_available_migrations()
        pending = self._get_pending_migrations()

        return {
            'total_available': len(available),
            'total_applied': len(applied),
            'total_pending': len(pending),
            'applied_versions': applied,
            'pending_versions': [m.version for m in pending]
        }
