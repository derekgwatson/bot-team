"""Database service for Chester - manages bot deployment configuration."""
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
from contextlib import contextmanager
from shared.migrations import MigrationRunner


class Database:
    """SQLite database manager for Chester."""

    def __init__(self, db_path: str = None, auto_migrate: bool = True):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'chester.db'
        self.db_path = db_path
        self.migrations_dir = Path(__file__).parent.parent / 'migrations'

        if auto_migrate:
            self.run_migrations()

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

    def run_migrations(self, verbose: bool = False):
        """Run database migrations."""
        runner = MigrationRunner(
            db_path=str(self.db_path),
            migrations_dir=str(self.migrations_dir)
        )
        runner.run_pending_migrations(verbose=verbose)

    def get_deployment_defaults(self) -> Dict:
        """Get the deployment defaults."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM deployment_defaults WHERE id = 1')
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {}

    def update_deployment_defaults(self, **kwargs) -> bool:
        """Update deployment defaults."""
        valid_fields = ['repo', 'path_template', 'service_template',
                       'domain_template', 'nginx_config_template', 'workers']

        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        if not updates:
            return False

        set_clause = ', '.join([f'{k} = ?' for k in updates.keys()])
        query = f'UPDATE deployment_defaults SET {set_clause} WHERE id = 1'

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, list(updates.values()))
            return cursor.rowcount > 0

    def add_bot(self, name: str, description: str, port: int, **kwargs) -> Optional[int]:
        """Add a new bot to the database."""
        valid_fields = ['repo', 'path', 'service', 'domain', 'nginx_config_name', 'workers', 'skip_nginx', 'public_facing']

        # Get deployment defaults
        defaults = self.get_deployment_defaults()

        # Apply defaults with template substitution
        bot_data = {
            'name': name,
            'description': description,
            'port': port,
            'repo': kwargs.get('repo', defaults.get('repo', '')),
            'path': kwargs.get('path', defaults['path_template'].format(bot_name=name)),
            'service': kwargs.get('service', defaults['service_template'].format(bot_name=name)),
            'domain': kwargs.get('domain', defaults['domain_template'].format(bot_name=name)),
            'nginx_config_name': kwargs.get('nginx_config_name', defaults['nginx_config_template'].format(bot_name=name)),
            'workers': kwargs.get('workers', defaults.get('workers', 3)),
            'skip_nginx': 1 if kwargs.get('skip_nginx', False) else 0,
            'public_facing': 1 if kwargs.get('public_facing', False) else 0
        }

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO bots
                (name, description, port, repo, path, service, domain, nginx_config_name, workers, skip_nginx, public_facing)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                bot_data['name'], bot_data['description'], bot_data['port'],
                bot_data['repo'], bot_data['path'], bot_data['service'],
                bot_data['domain'], bot_data['nginx_config_name'],
                bot_data['workers'], bot_data['skip_nginx'], bot_data['public_facing']
            ))
            return cursor.lastrowid

    def get_bot(self, name: str) -> Optional[Dict]:
        """Get a bot by name."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM bots WHERE name = ?', (name,))
            row = cursor.fetchone()
            if row:
                bot = dict(row)
                bot['skip_nginx'] = bool(bot['skip_nginx'])
                bot['public_facing'] = bool(bot.get('public_facing', 0))
                return bot
            return None

    def get_all_bots(self) -> List[Dict]:
        """Get all bots."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM bots ORDER BY name')
            rows = cursor.fetchall()
            bots = []
            for row in rows:
                bot = dict(row)
                bot['skip_nginx'] = bool(bot['skip_nginx'])
                bot['public_facing'] = bool(bot.get('public_facing', 0))
                bots.append(bot)
            return bots

    def get_public_bots(self) -> List[Dict]:
        """Get only public-facing bots (for company-wide access)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM bots WHERE public_facing = 1 ORDER BY name')
            rows = cursor.fetchall()
            bots = []
            for row in rows:
                bot = dict(row)
                bot['skip_nginx'] = bool(bot['skip_nginx'])
                bot['public_facing'] = bool(bot.get('public_facing', 0))
                bots.append(bot)
            return bots

    def update_bot(self, name: str, **kwargs) -> bool:
        """Update a bot's configuration."""
        valid_fields = ['description', 'port', 'repo', 'path', 'service',
                       'domain', 'nginx_config_name', 'workers', 'skip_nginx', 'public_facing']

        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        if not updates:
            return False

        # Convert boolean fields to int
        if 'skip_nginx' in updates:
            updates['skip_nginx'] = 1 if updates['skip_nginx'] else 0
        if 'public_facing' in updates:
            updates['public_facing'] = 1 if updates['public_facing'] else 0

        updates['updated_at'] = 'CURRENT_TIMESTAMP'
        set_clause = ', '.join([f'{k} = ?' for k in updates.keys()])
        query = f'UPDATE bots SET {set_clause} WHERE name = ?'

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, list(updates.values()) + [name])
            return cursor.rowcount > 0

    def delete_bot(self, name: str) -> bool:
        """Delete a bot from the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM bots WHERE name = ?', (name,))
            return cursor.rowcount > 0

    def get_bot_deployment_config(self, name: str) -> Optional[Dict]:
        """Get deployment configuration for a specific bot (for Dorothy)."""
        bot = self.get_bot(name)
        if not bot:
            return None

        return {
            'name': bot['name'],
            'description': bot['description'],
            'port': bot['port'],
            'repo': bot['repo'],
            'path': bot['path'],
            'service': bot['service'],
            'domain': bot['domain'],
            'nginx_config_name': bot['nginx_config_name'],
            'workers': bot['workers'],
            'skip_nginx': bot['skip_nginx'],
            'public_facing': bot['public_facing']
        }


# Global database instance
db = Database()
