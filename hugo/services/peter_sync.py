"""
Service for syncing Buz access changes to Peter.

When Hugo toggles a user's Buz access, it updates Peter's staff database
to keep the buz_access field in sync.
"""
import os
import logging
from typing import Dict, Any, List, Optional
from shared.http_client import BotHttpClient
from shared.config.ports import get_port

logger = logging.getLogger(__name__)


class PeterSyncService:
    """
    Syncs Buz access changes to Peter's staff database.

    When a user's Buz access is changed in Hugo, this service
    updates Peter to keep the systems in sync.
    """

    def __init__(self):
        """Initialize Peter sync service."""
        peter_port = get_port('peter')
        peter_url = os.environ.get('PETER_URL', f'http://localhost:{peter_port}')
        self.client = BotHttpClient(peter_url, timeout=30)

    def get_staff_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Look up a staff member by email in Peter.

        Args:
            email: Email address to search for

        Returns:
            Staff record dict or None
        """
        try:
            response = self.client.get('/api/staff', params={'name': email})
            if response.status_code == 200:
                data = response.json()
                staff_list = data.get('staff', [])
                # Search for exact email match
                for staff in staff_list:
                    if (staff.get('work_email', '').lower() == email.lower() or
                        staff.get('personal_email', '').lower() == email.lower() or
                        staff.get('google_primary_email', '').lower() == email.lower()):
                        return staff
            return None
        except Exception as e:
            logger.error(f"Error looking up staff {email} in Peter: {e}")
            return None

    def update_buz_access(
        self,
        staff_id: int,
        buz_access: bool,
        buz_orgs: Optional[List[str]] = None,
        modified_by: str = 'hugo'
    ) -> Dict[str, Any]:
        """
        Update a staff member's Buz access in Peter.

        Args:
            staff_id: Peter staff ID
            buz_access: Whether user has any Buz access
            buz_orgs: List of org keys the user has access to (for multi-store)
            modified_by: Who made the change

        Returns:
            Result dict with success status
        """
        try:
            # Build update payload
            payload = {
                'buz_access': buz_access,
                'modified_by': modified_by
            }

            # If we have org-specific access info, include it
            # (This requires Peter migration to support buz_orgs field)
            if buz_orgs is not None:
                payload['buz_orgs'] = ','.join(buz_orgs) if buz_orgs else ''

            response = self.client.patch(f'/api/staff/{staff_id}', json=payload)

            if response.status_code == 200:
                return {
                    'success': True,
                    'staff_id': staff_id,
                    'buz_access': buz_access
                }
            else:
                return {
                    'success': False,
                    'error': f"Peter returned status {response.status_code}"
                }

        except Exception as e:
            logger.error(f"Error updating staff {staff_id} Buz access in Peter: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def sync_user_access(
        self,
        email: str,
        is_active: bool,
        org_key: str,
        all_user_orgs: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Sync a user's Buz access change to Peter.

        This is called after successfully toggling access in Buz.

        Args:
            email: User's email
            is_active: New active status in Buz
            org_key: Org where access was changed
            all_user_orgs: All orgs the user currently has access to

        Returns:
            Result dict
        """
        # Look up staff in Peter
        staff = self.get_staff_by_email(email)

        if not staff:
            logger.info(f"Staff {email} not found in Peter, skipping sync")
            return {
                'success': True,
                'skipped': True,
                'reason': 'Staff not found in Peter'
            }

        staff_id = staff['id']

        # Determine overall buz_access (any org = True)
        has_any_access = is_active or (all_user_orgs and len(all_user_orgs) > 0)

        # Update Peter
        result = self.update_buz_access(
            staff_id=staff_id,
            buz_access=has_any_access,
            buz_orgs=all_user_orgs,
            modified_by='hugo'
        )

        if result['success']:
            logger.info(f"Synced Buz access for {email} to Peter: {has_any_access}")
        else:
            logger.error(f"Failed to sync Buz access for {email} to Peter: {result.get('error')}")

        return result


# Singleton instance
peter_sync = PeterSyncService()
