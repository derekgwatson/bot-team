"""Permission management service for Grant."""
import logging
from typing import Dict, List, Optional
from config import config
from database.db import get_db
from shared.http_client import BotHttpClient

logger = logging.getLogger(__name__)


class PermissionService:
    """Service for managing bot access permissions."""

    def __init__(self):
        self.superadmins = config.superadmins

    def _get_db(self):
        """Get database instance."""
        return get_db()

    # ─────────────────────────────────────────────────────────────
    # Access Checking
    # ─────────────────────────────────────────────────────────────

    def check_access(self, email: str, bot_name: str) -> Dict:
        """
        Check if a user has access to a bot.

        Superadmins always have admin access to everything.

        Returns: {allowed: bool, role: str|None, is_admin: bool}
        """
        email = email.lower().strip()
        bot_name = bot_name.lower().strip()

        # Superadmins always have admin access
        if email in self.superadmins:
            return {
                'allowed': True,
                'role': 'admin',
                'is_admin': True,
                'source': 'superadmin'
            }

        # Check database
        result = self._get_db().check_access(email, bot_name)
        result['source'] = 'database' if result['allowed'] else None
        return result

    def is_superadmin(self, email: str) -> bool:
        """Check if email is a superadmin."""
        return email.lower().strip() in self.superadmins

    # ─────────────────────────────────────────────────────────────
    # Permission Management
    # ─────────────────────────────────────────────────────────────

    def grant_permission(
        self,
        email: str,
        bot_name: str,
        role: str,
        granted_by: str
    ) -> Dict:
        """
        Grant or update permission for a user on a bot.

        Args:
            email: User's email address
            bot_name: Bot name (e.g., 'fiona') or '*' for all bots
            role: 'user' or 'admin'
            granted_by: Email of person granting permission

        Returns:
            Permission record
        """
        logger.info(f"Granting {role} access to {email} for {bot_name} by {granted_by}")
        return self._get_db().grant_permission(email, bot_name, role, granted_by)

    def revoke_permission(
        self,
        email: str,
        bot_name: str,
        revoked_by: str
    ) -> bool:
        """
        Revoke permission for a user on a bot.

        Returns: True if revoked, False if no permission existed
        """
        logger.info(f"Revoking access from {email} for {bot_name} by {revoked_by}")
        return self._get_db().revoke_permission(email, bot_name, revoked_by)

    def get_user_permissions(self, email: str) -> List[Dict]:
        """Get all permissions for a user."""
        return self._get_db().get_permissions_for_user(email)

    def get_bot_permissions(self, bot_name: str) -> List[Dict]:
        """Get all permissions for a bot."""
        return self._get_db().get_permissions_for_bot(bot_name)

    def get_all_permissions(self) -> List[Dict]:
        """Get all permissions."""
        return self._get_db().get_all_permissions()

    # ─────────────────────────────────────────────────────────────
    # Audit
    # ─────────────────────────────────────────────────────────────

    def get_audit_log(
        self,
        email: str = None,
        bot_name: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get audit log entries."""
        return self._get_db().get_audit_log(email, bot_name, limit)

    # ─────────────────────────────────────────────────────────────
    # Bot Registry
    # ─────────────────────────────────────────────────────────────

    def sync_bots_from_chester(self) -> Dict:
        """
        Sync bot registry from Chester.

        Returns: {success: bool, synced: int, error: str|None}
        """
        try:
            chester_url = config.get_chester_url()
            client = BotHttpClient(chester_url, timeout=10)

            response = client.get('/api/bots')
            response.raise_for_status()

            data = response.json()
            bots = data.get('bots', [])

            if not bots:
                logger.warning("No bots returned from Chester")
                return {'success': False, 'error': 'No bots returned from Chester'}

            result = self._get_db().sync_bots(bots)
            logger.info(f"Synced {result['synced']} bots from Chester")

            return {
                'success': True,
                'synced': result['synced'],
                'synced_at': result['synced_at']
            }

        except Exception as e:
            logger.exception(f"Failed to sync bots from Chester: {e}")
            return {'success': False, 'error': str(e)}

    def get_bots(self) -> List[Dict]:
        """Get all registered bots."""
        return self._get_db().get_bots()

    def get_bot(self, name: str) -> Optional[Dict]:
        """Get a bot by name."""
        return self._get_db().get_bot(name)

    # ─────────────────────────────────────────────────────────────
    # Stats
    # ─────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """Get statistics about permissions."""
        stats = self._get_db().get_stats()
        stats['superadmins'] = len(self.superadmins)
        return stats

    def get_unique_users(self) -> List[str]:
        """Get list of unique user emails with permissions."""
        return self._get_db().get_unique_users()


# Global service instance
permission_service = PermissionService()
