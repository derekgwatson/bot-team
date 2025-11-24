"""
Service to sync allstaff Google Group with Peter's database
"""
import threading
import time
from services.peter_client import peter_client
from services.google_groups import groups_service


class SyncService:
    """
    Background service that periodically syncs the allstaff Google Group
    with the member list from Peter
    """

    def __init__(self, interval_seconds=300):  # Default: sync every 5 minutes
        self.interval_seconds = interval_seconds
        self.running = False
        self.thread = None
        self.last_sync = None
        self.last_sync_result = None

    def start(self):
        """Start the background sync thread"""
        if self.running:
            print("Sync service is already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.thread.start()
        print(f"✓ Sync service started (interval: {self.interval_seconds}s)")

    def stop(self):
        """Stop the background sync thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("✓ Sync service stopped")

    def _sync_loop(self):
        """Background loop that syncs periodically"""
        while self.running:
            try:
                self.sync_now()
            except Exception as e:
                print(f"Error in sync loop: {e}")
                import traceback
                traceback.print_exc()

            # Sleep in small increments so we can stop quickly
            for _ in range(self.interval_seconds):
                if not self.running:
                    break
                time.sleep(1)

    def sync_now(self):
        """
        Perform a sync right now

        Returns:
            Dict with sync results
        """
        print("Starting allstaff group sync...")
        start_time = time.time()

        # Get desired members from Peter
        desired_emails = peter_client.get_allstaff_emails()
        print(f"Peter says {len(desired_emails)} people should be in allstaff")

        if not desired_emails:
            print("Warning: Peter returned no emails. Skipping sync to avoid emptying the group.")
            return {
                'success': False,
                'error': 'No emails returned from Peter',
                'timestamp': time.time()
            }

        # Get current members from Google Group
        current_members = groups_service.get_all_members()
        # Filter out members with None email (can happen with nested groups or special types)
        current_emails = {m['email'].lower() for m in current_members if m.get('email')}
        print(f"Google Group currently has {len(current_emails)} members")

        # Convert desired to lowercase for comparison
        desired_emails_set = {e.lower() for e in desired_emails}

        # Find who to add and who to remove
        to_add = desired_emails_set - current_emails
        to_remove = current_emails - desired_emails_set

        print(f"Need to add {len(to_add)}, remove {len(to_remove)}")

        # Perform additions
        added = []
        add_errors = []
        for email in to_add:
            result = groups_service.add_member(email)
            if 'error' in result:
                add_errors.append({'email': email, 'error': result['error']})
                print(f"  ✗ Failed to add {email}: {result['error']}")
            else:
                added.append(email)
                print(f"  ✓ Added {email}")

        # Perform removals
        removed = []
        remove_errors = []
        for email in to_remove:
            result = groups_service.remove_member(email)
            if 'error' in result:
                remove_errors.append({'email': email, 'error': result['error']})
                print(f"  ✗ Failed to remove {email}: {result['error']}")
            else:
                removed.append(email)
                print(f"  ✓ Removed {email}")

        elapsed = time.time() - start_time

        result = {
            'success': True,
            'timestamp': time.time(),
            'elapsed_seconds': round(elapsed, 2),
            'desired_count': len(desired_emails_set),
            'current_count': len(current_emails),
            'added': added,
            'removed': removed,
            'add_errors': add_errors,
            'remove_errors': remove_errors
        }

        self.last_sync = time.time()
        self.last_sync_result = result

        print(f"Sync complete in {elapsed:.2f}s")
        return result

    def get_status(self):
        """Get sync service status"""
        return {
            'running': self.running,
            'interval_seconds': self.interval_seconds,
            'last_sync': self.last_sync,
            'last_sync_result': self.last_sync_result
        }


# Singleton instance
sync_service = SyncService()
