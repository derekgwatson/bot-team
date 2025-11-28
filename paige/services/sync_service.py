"""
Sync service for keeping DokuWiki users in sync with Peter staff directory.

Peter is authoritative - wiki users are added/removed based on Peter's staff data.
Admin users in the wiki are never removed (safety measure).
"""
import logging
import re
from typing import Dict, List, Set

from shared.http_client import BotHttpClient
from shared.config.ports import get_port
from services.dokuwiki_service import DokuWikiService

logger = logging.getLogger(__name__)


class SyncService:
    """Service for syncing wiki users with Peter staff directory."""

    def __init__(self, wiki_service: DokuWikiService):
        """
        Initialize the sync service.

        Args:
            wiki_service: DokuWiki service instance for user management
        """
        self.wiki_service = wiki_service
        self._peter_client = None

    @property
    def peter_client(self) -> BotHttpClient:
        """Lazy-load Peter client."""
        if self._peter_client is None:
            peter_port = get_port('peter')
            self._peter_client = BotHttpClient(
                f"http://localhost:{peter_port}",
                timeout=30
            )
        return self._peter_client

    def _generate_login(self, name: str) -> str:
        """
        Generate a wiki login from a full name.

        Converts "John Smith" to "john.smith"
        Handles multiple names like "John van der Berg" -> "john.van.der.berg"
        Removes special characters.

        Args:
            name: Full name of the staff member

        Returns:
            Lowercase login string with dots separating name parts
        """
        if not name:
            return ""

        # Convert to lowercase and split on whitespace
        parts = name.lower().split()

        # Remove any characters that aren't alphanumeric
        clean_parts = []
        for part in parts:
            clean = re.sub(r'[^a-z0-9]', '', part)
            if clean:
                clean_parts.append(clean)

        return '.'.join(clean_parts)

    def _get_peter_staff(self) -> List[Dict]:
        """
        Get all active staff from Peter.

        All active staff should have wiki access.

        Returns:
            List of active staff dicts
        """
        try:
            response = self.peter_client.get('/api/staff', params={'status': 'active'})
            response.raise_for_status()
            data = response.json()

            staff = data.get('staff', [])
            logger.info(f"Found {len(staff)} active staff in Peter")
            return staff

        except Exception as e:
            logger.exception(f"Failed to get staff from Peter: {e}")
            raise

    def _get_email_for_staff(self, staff: Dict) -> str:
        """
        Get the appropriate email for a staff member.

        Priority for Google users:
        1. google_primary_email
        2. work_email (fallback if primary missing)
        3. personal_email (final fallback)

        Priority for non-Google users:
        1. work_email
        2. personal_email

        Args:
            staff: Staff dict from Peter

        Returns:
            Email address to use for wiki account
        """
        if staff.get('google_access') == 1:
            # Google users: prefer google_primary_email, fall back to others
            return (staff.get('google_primary_email') or
                    staff.get('work_email') or
                    staff.get('personal_email') or '')
        else:
            # Non-Google users: work_email first, then personal_email
            return staff.get('work_email') or staff.get('personal_email') or ''

    def sync(self) -> Dict:
        """
        Sync wiki users with Peter staff directory.

        - Adds staff with wiki_access who aren't in the wiki
        - Removes wiki users who aren't in Peter or lost wiki_access
        - Never removes users in the admin group

        Returns:
            Dict with sync results including added, removed, errors
        """
        result = {
            'success': True,
            'added': [],
            'removed': [],
            'skipped_admins': [],
            'errors': [],
            'staff_count': 0,
            'wiki_count_before': 0,
            'wiki_count_after': 0,
        }

        try:
            # Get current wiki users
            wiki_users = self.wiki_service.get_all_users()
            result['wiki_count_before'] = len(wiki_users)

            # Build lookup of wiki users by login
            wiki_by_login: Dict[str, any] = {u.login.lower(): u for u in wiki_users}

            # Identify admin users (never remove these)
            admin_logins: Set[str] = {
                u.login.lower() for u in wiki_users
                if 'admin' in u.groups
            }
            logger.info(f"Found {len(admin_logins)} admin users who will be protected")

            # Get staff from Peter who should have wiki access
            peter_staff = self._get_peter_staff()
            result['staff_count'] = len(peter_staff)

            # Build set of logins that should exist (from Peter)
            expected_logins: Set[str] = set()

            # Add missing users
            for staff in peter_staff:
                name = staff.get('name', '')
                login = self._generate_login(name)

                if not login:
                    result['errors'].append(f"Could not generate login for staff: {name}")
                    continue

                email = self._get_email_for_staff(staff)
                if not email:
                    result['errors'].append(
                        f"No email available for {name} (login: {login})"
                    )
                    continue

                expected_logins.add(login)

                # Check if user already exists
                if login in wiki_by_login:
                    continue  # Already exists

                # Add new user
                add_result = self.wiki_service.add_user(
                    login=login,
                    name=name,
                    email=email
                )

                if add_result['success']:
                    result['added'].append({
                        'login': login,
                        'name': name,
                        'email': email
                    })
                    logger.info(f"Added wiki user: {login} ({email})")
                else:
                    result['errors'].append(
                        f"Failed to add {login}: {add_result.get('error')}"
                    )

            # Remove users no longer in Peter (but not admins)
            for login, wiki_user in wiki_by_login.items():
                if login in expected_logins:
                    continue  # Should exist

                if login in admin_logins:
                    result['skipped_admins'].append(login)
                    logger.info(f"Skipping removal of admin user: {login}")
                    continue

                # Remove user
                remove_result = self.wiki_service.remove_user(login)

                if remove_result['success']:
                    result['removed'].append({
                        'login': login,
                        'name': wiki_user.name,
                        'email': wiki_user.email
                    })
                    logger.info(f"Removed wiki user: {login}")
                else:
                    result['errors'].append(
                        f"Failed to remove {login}: {remove_result.get('error')}"
                    )

            # Get final count
            result['wiki_count_after'] = len(self.wiki_service.get_all_users())

            if result['errors']:
                result['success'] = len(result['errors']) < len(peter_staff)

            logger.info(
                f"Sync complete: added={len(result['added'])}, "
                f"removed={len(result['removed'])}, "
                f"skipped_admins={len(result['skipped_admins'])}, "
                f"errors={len(result['errors'])}"
            )

        except Exception as e:
            logger.exception(f"Sync failed: {e}")
            result['success'] = False
            result['errors'].append(str(e))

        return result

    def preview(self) -> Dict:
        """
        Preview what a sync would do without making changes.

        Returns:
            Dict showing what would be added/removed
        """
        result = {
            'would_add': [],
            'would_remove': [],
            'would_skip_admins': [],
            'errors': [],
        }

        try:
            # Get current wiki users
            wiki_users = self.wiki_service.get_all_users()
            wiki_by_login = {u.login.lower(): u for u in wiki_users}
            admin_logins = {u.login.lower() for u in wiki_users if 'admin' in u.groups}

            # Get staff from Peter
            peter_staff = self._get_peter_staff()
            expected_logins: Set[str] = set()

            # Check what would be added
            for staff in peter_staff:
                name = staff.get('name', '')
                login = self._generate_login(name)

                if not login:
                    result['errors'].append(f"Could not generate login for: {name}")
                    continue

                email = self._get_email_for_staff(staff)
                if not email:
                    result['errors'].append(f"No email for: {name}")
                    continue

                expected_logins.add(login)

                if login not in wiki_by_login:
                    result['would_add'].append({
                        'login': login,
                        'name': name,
                        'email': email
                    })

            # Check what would be removed
            for login, wiki_user in wiki_by_login.items():
                if login in expected_logins:
                    continue

                if login in admin_logins:
                    result['would_skip_admins'].append(login)
                else:
                    result['would_remove'].append({
                        'login': login,
                        'name': wiki_user.name,
                        'email': wiki_user.email
                    })

        except Exception as e:
            logger.exception(f"Preview failed: {e}")
            result['errors'].append(str(e))

        return result
