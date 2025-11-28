"""
DokuWiki User Management Service.

Manages users in DokuWiki's flat-file user database (conf/users.auth.php).

File format (each line):
    login:passwordhash:Real Name:email:groups

For Google Auth users, password is '*' (external auth).
Groups are comma-separated.
"""
import os
import re
import logging
import fcntl
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WikiUser:
    """Represents a DokuWiki user."""
    login: str
    name: str
    email: str
    groups: List[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'login': self.login,
            'name': self.name,
            'email': self.email,
            'groups': self.groups,
        }

    def to_auth_line(self) -> str:
        """Convert to DokuWiki users.auth.php line format."""
        # Password is '*' for external auth (Google)
        groups_str = ','.join(self.groups)
        return f"{self.login}:*:{self.name}:{self.email}:{groups_str}"


class DokuWikiService:
    """Service for managing DokuWiki users via filesystem."""

    def __init__(self, dokuwiki_path: str, default_groups: List[str] = None):
        """
        Initialize the DokuWiki service.

        Args:
            dokuwiki_path: Path to DokuWiki installation (e.g., /var/www/dokuwiki)
            default_groups: Default groups for new users (e.g., ['user', 'google'])
        """
        self.dokuwiki_path = Path(dokuwiki_path)
        self.users_file = self.dokuwiki_path / "conf" / "users.auth.php"
        self.default_groups = default_groups or ['user', 'google']

    def _validate_path(self) -> bool:
        """Check if DokuWiki path and users file exist."""
        if not self.dokuwiki_path.exists():
            logger.error(f"DokuWiki path does not exist: {self.dokuwiki_path}")
            return False
        if not self.users_file.exists():
            logger.error(f"Users file does not exist: {self.users_file}")
            return False
        return True

    def _parse_user_line(self, line: str) -> Optional[WikiUser]:
        """
        Parse a line from users.auth.php into a WikiUser.

        Format: login:passwordhash:Real Name:email:groups
        """
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith('#') or line.startswith('//'):
            return None

        # Skip PHP tags
        if line.startswith('<?') or line.startswith('?>'):
            return None

        parts = line.split(':')
        if len(parts) < 5:
            logger.warning(f"Invalid user line (not enough parts): {line}")
            return None

        login = parts[0]
        # parts[1] is password hash (we don't need it)
        name = parts[2]
        email = parts[3]
        groups = parts[4].split(',') if parts[4] else []

        return WikiUser(
            login=login,
            name=name,
            email=email,
            groups=groups
        )

    def _read_users_file(self) -> tuple[List[str], List[WikiUser]]:
        """
        Read and parse the users.auth.php file.

        Returns:
            Tuple of (raw_lines, parsed_users)
            raw_lines includes comments and PHP tags for preservation
        """
        if not self._validate_path():
            return [], []

        with open(self.users_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        users = []
        for line in lines:
            user = self._parse_user_line(line)
            if user:
                users.append(user)

        return lines, users

    def _write_users_file(self, lines: List[str]) -> bool:
        """
        Write lines to users.auth.php with file locking.

        Args:
            lines: All lines to write (including comments/PHP tags)

        Returns:
            True if successful, False otherwise
        """
        if not self._validate_path():
            return False

        try:
            # Use file locking to prevent concurrent writes
            with open(self.users_file, 'w', encoding='utf-8') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.writelines(lines)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return True
        except Exception as e:
            logger.exception(f"Failed to write users file: {e}")
            return False

    def get_all_users(self) -> List[WikiUser]:
        """Get all users from DokuWiki."""
        _, users = self._read_users_file()
        return users

    def get_user(self, login: str) -> Optional[WikiUser]:
        """Get a specific user by login."""
        users = self.get_all_users()
        for user in users:
            if user.login.lower() == login.lower():
                return user
        return None

    def user_exists(self, login: str) -> bool:
        """Check if a user exists."""
        return self.get_user(login) is not None

    def add_user(self, login: str, name: str, email: str,
                 groups: List[str] = None) -> Dict:
        """
        Add a new user to DokuWiki.

        Args:
            login: Username (typically firstname.lastname)
            name: Full display name
            email: Email address
            groups: List of groups (defaults to default_groups from config)

        Returns:
            Dict with success status and user data or error
        """
        # Validate login format (alphanumeric, dots, underscores, hyphens)
        if not re.match(r'^[a-zA-Z0-9._-]+$', login):
            return {
                'success': False,
                'error': f"Invalid login format: {login}. Use only letters, numbers, dots, underscores, hyphens."
            }

        # Check if user already exists
        if self.user_exists(login):
            return {
                'success': False,
                'error': f"User already exists: {login}"
            }

        # Use default groups if not specified
        if groups is None:
            groups = self.default_groups.copy()

        # Create the new user
        new_user = WikiUser(
            login=login.lower(),
            name=name,
            email=email,
            groups=groups
        )

        # Read current file
        lines, _ = self._read_users_file()

        # Add new user line before the closing PHP tag (if present)
        new_line = new_user.to_auth_line() + '\n'

        # Find where to insert (before ?> if present, otherwise at end)
        insert_index = len(lines)
        for i, line in enumerate(lines):
            if line.strip() == '?>':
                insert_index = i
                break

        lines.insert(insert_index, new_line)

        # Write back
        if self._write_users_file(lines):
            logger.info(f"Added wiki user: {login} ({email})")
            return {
                'success': True,
                'user': new_user.to_dict()
            }
        else:
            return {
                'success': False,
                'error': "Failed to write users file"
            }

    def remove_user(self, login: str) -> Dict:
        """
        Remove a user from DokuWiki.

        Args:
            login: Username to remove

        Returns:
            Dict with success status
        """
        # Check if user exists
        existing_user = self.get_user(login)
        if not existing_user:
            return {
                'success': False,
                'error': f"User not found: {login}"
            }

        # Read current file
        lines, _ = self._read_users_file()

        # Filter out the user's line
        new_lines = []
        removed = False
        for line in lines:
            parsed = self._parse_user_line(line)
            if parsed and parsed.login.lower() == login.lower():
                removed = True
                continue  # Skip this line
            new_lines.append(line)

        if not removed:
            return {
                'success': False,
                'error': f"Could not find user line to remove: {login}"
            }

        # Write back
        if self._write_users_file(new_lines):
            logger.info(f"Removed wiki user: {login}")
            return {
                'success': True,
                'removed_user': existing_user.to_dict()
            }
        else:
            return {
                'success': False,
                'error': "Failed to write users file"
            }

    def get_health_status(self) -> Dict:
        """
        Get health status of the DokuWiki service.

        Returns:
            Dict with health information
        """
        status = {
            'dokuwiki_path': str(self.dokuwiki_path),
            'users_file': str(self.users_file),
            'path_exists': self.dokuwiki_path.exists(),
            'users_file_exists': self.users_file.exists(),
            'users_file_readable': False,
            'users_file_writable': False,
            'user_count': 0,
        }

        if status['users_file_exists']:
            status['users_file_readable'] = os.access(self.users_file, os.R_OK)
            status['users_file_writable'] = os.access(self.users_file, os.W_OK)

            if status['users_file_readable']:
                users = self.get_all_users()
                status['user_count'] = len(users)

        status['healthy'] = (
            status['path_exists'] and
            status['users_file_exists'] and
            status['users_file_readable'] and
            status['users_file_writable']
        )

        return status
