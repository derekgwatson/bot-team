"""
Sync service for coordinating inventory and pricing data synchronization.

Orchestrates browser exports, parsing, and database updates.
"""
import logging
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from database.db import inventory_db
from services.browser_service import BuzExportService, run_async
from services.parser_service import parser

logger = logging.getLogger(__name__)


class SyncService:
    """
    Service for synchronizing inventory and pricing data from Buz.

    Coordinates the browser service, parser, and database operations.
    """

    def __init__(self, config):
        """
        Initialize the sync service.

        Args:
            config: Bot configuration object
        """
        self.config = config
        self.db = inventory_db

    def _do_inventory_sync(
        self,
        org_key: str,
        sync_id: int,
        include_inactive: bool = True,
        performed_by: str = 'system'
    ) -> Dict[str, Any]:
        """
        Perform the actual inventory sync work.

        Called by background thread with an existing sync_id.

        Args:
            org_key: Organization key to sync
            sync_id: Existing sync log ID
            include_inactive: Include inactive items
            performed_by: Who initiated the sync

        Returns:
            Dict with sync results
        """
        logger.info(f"Performing inventory sync for {org_key} (sync_id={sync_id})")
        start_time = time.time()

        try:
            # Stage 1: Export from Buz (0-40%)
            self.db.update_sync_progress(sync_id, 5, 'Connecting to Buz...')
            export_service = BuzExportService(
                self.config,
                headless=self.config.browser_headless
            )

            self.db.update_sync_progress(sync_id, 10, 'Exporting inventory from Buz...')
            export_result = run_async(
                export_service.export_inventory(org_key, include_inactive)
            )

            if not export_result['success']:
                duration = time.time() - start_time
                self.db.complete_sync(
                    sync_id,
                    item_count=0,
                    status='failed',
                    error_message=export_result.get('error', 'Export failed'),
                    duration_seconds=duration
                )
                return export_result

            file_path = export_result['file_path']
            self.db.update_sync_progress(sync_id, 40, 'Parsing Excel file...')

            # Stage 2: Parse the exported file (40-70%)
            parse_result = parser.parse_inventory_file(file_path)

            if not parse_result['success']:
                duration = time.time() - start_time
                self.db.complete_sync(
                    sync_id,
                    item_count=0,
                    status='failed',
                    error_message=parse_result.get('error', 'Parse failed'),
                    duration_seconds=duration
                )
                return parse_result

            items = parse_result['items']
            groups = parse_result['groups']
            self.db.update_sync_progress(sync_id, 70, f'Parsed {len(items)} items from {len(groups)} groups')

            # Stage 3: Update inventory groups in database (70-80%)
            self.db.update_sync_progress(sync_id, 75, f'Updating {len(groups)} groups...')
            for group in groups:
                group_code = group['group_code']
                self.db.upsert_inventory_group(
                    org_key=org_key,
                    group_code=group_code,
                    group_name=group['group_name'],
                    item_count=group.get('item_count', 0),
                    home_org=self.config.get_home_org(group_code)
                )

            # Stage 4: Bulk upsert items to database (80-100%)
            self.db.update_sync_progress(sync_id, 80, f'Saving {len(items)} items to database...')
            db_result = self.db.bulk_upsert_inventory_items(org_key, items)
            self.db.update_sync_progress(sync_id, 95, 'Finalizing...')

            duration = time.time() - start_time

            # Complete sync log
            self.db.complete_sync(
                sync_id,
                item_count=len(items),
                status='success',
                duration_seconds=duration
            )

            # Log activity
            self.db.log_activity(
                action='sync_inventory',
                entity_type='inventory',
                entity_id=org_key,
                org_key=org_key,
                new_value=f'{len(items)} items synced',
                performed_by=performed_by
            )

            # Clean up temp file
            try:
                Path(file_path).unlink()
            except Exception:
                pass

            logger.info(f"Inventory sync completed for {org_key}: {len(items)} items in {duration:.1f}s")

            return {
                'success': True,
                'org_key': org_key,
                'items_synced': len(items),
                'groups_synced': len(groups),
                'created': db_result['created'],
                'updated': db_result['updated'],
                'duration_seconds': duration
            }

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.exception(f"Inventory sync failed for {org_key}: {error_msg}")

            self.db.complete_sync(
                sync_id,
                item_count=0,
                status='failed',
                error_message=error_msg,
                duration_seconds=duration
            )

            return {
                'success': False,
                'error': error_msg,
                'org_key': org_key
            }

    def sync_inventory(
        self,
        org_key: str,
        include_inactive: bool = True,
        performed_by: str = 'system'
    ) -> Dict[str, Any]:
        """
        Sync inventory items from Buz for an organization (synchronous).

        Note: For async operation, use the API endpoint which runs in background.

        Args:
            org_key: Organization key to sync
            include_inactive: Include inactive items
            performed_by: Who initiated the sync

        Returns:
            Dict with sync results
        """
        # Check for running sync
        running_syncs = self.db.get_running_syncs(org_key)
        if any(s['sync_type'] == 'inventory' for s in running_syncs):
            return {
                'success': False,
                'error': 'Inventory sync already in progress for this org'
            }

        # Start sync log and perform sync
        sync_id = self.db.start_sync(org_key, 'inventory')
        return self._do_inventory_sync(org_key, sync_id, include_inactive, performed_by)

    def _do_pricing_sync(
        self,
        org_key: str,
        sync_id: int,
        include_inactive: bool = True,
        performed_by: str = 'system'
    ) -> Dict[str, Any]:
        """
        Perform the actual pricing sync work.

        Called by background thread with an existing sync_id.

        Args:
            org_key: Organization key to sync
            sync_id: Existing sync log ID
            include_inactive: Include inactive pricing
            performed_by: Who initiated the sync

        Returns:
            Dict with sync results
        """
        logger.info(f"Performing pricing sync for {org_key} (sync_id={sync_id})")
        start_time = time.time()

        try:
            # Stage 1: Export from Buz (0-40%)
            self.db.update_sync_progress(sync_id, 5, 'Connecting to Buz...')
            export_service = BuzExportService(
                self.config,
                headless=self.config.browser_headless
            )

            self.db.update_sync_progress(sync_id, 10, 'Exporting pricing from Buz...')
            export_result = run_async(
                export_service.export_pricing(org_key, include_inactive)
            )

            if not export_result['success']:
                duration = time.time() - start_time
                self.db.complete_sync(
                    sync_id,
                    item_count=0,
                    status='failed',
                    error_message=export_result.get('error', 'Export failed'),
                    duration_seconds=duration
                )
                return export_result

            file_path = export_result['file_path']
            self.db.update_sync_progress(sync_id, 40, 'Parsing Excel file...')

            # Stage 2: Parse the exported file (40-70%)
            parse_result = parser.parse_pricing_file(file_path)

            if not parse_result['success']:
                duration = time.time() - start_time
                self.db.complete_sync(
                    sync_id,
                    item_count=0,
                    status='failed',
                    error_message=parse_result.get('error', 'Parse failed'),
                    duration_seconds=duration
                )
                return parse_result

            coefficients = parse_result['coefficients']
            groups = parse_result['groups']
            self.db.update_sync_progress(sync_id, 70, f'Parsed {len(coefficients)} coefficients from {len(groups)} groups')

            # Stage 3: Update pricing groups in database (70-80%)
            self.db.update_sync_progress(sync_id, 75, f'Updating {len(groups)} groups...')
            for group in groups:
                self.db.upsert_pricing_group(
                    org_key=org_key,
                    group_code=group['group_code'],
                    group_name=group['group_name'],
                    coefficient_count=group.get('coefficient_count', 0)
                )

            # Stage 4: Bulk upsert coefficients to database (80-100%)
            self.db.update_sync_progress(sync_id, 80, f'Saving {len(coefficients)} coefficients to database...')
            db_result = self.db.bulk_upsert_pricing_coefficients(org_key, coefficients)
            self.db.update_sync_progress(sync_id, 95, 'Finalizing...')

            duration = time.time() - start_time

            # Complete sync log
            self.db.complete_sync(
                sync_id,
                item_count=len(coefficients),
                status='success',
                duration_seconds=duration
            )

            # Log activity
            self.db.log_activity(
                action='sync_pricing',
                entity_type='pricing',
                entity_id=org_key,
                org_key=org_key,
                new_value=f'{len(coefficients)} coefficients synced',
                performed_by=performed_by
            )

            # Clean up temp file
            try:
                Path(file_path).unlink()
            except Exception:
                pass

            logger.info(f"Pricing sync completed for {org_key}: {len(coefficients)} coefficients in {duration:.1f}s")

            return {
                'success': True,
                'org_key': org_key,
                'coefficients_synced': len(coefficients),
                'groups_synced': len(groups),
                'created': db_result['created'],
                'updated': db_result['updated'],
                'duration_seconds': duration
            }

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logger.exception(f"Pricing sync failed for {org_key}: {error_msg}")

            self.db.complete_sync(
                sync_id,
                item_count=0,
                status='failed',
                error_message=error_msg,
                duration_seconds=duration
            )

            return {
                'success': False,
                'error': error_msg,
                'org_key': org_key
            }

    def sync_pricing(
        self,
        org_key: str,
        include_inactive: bool = True,
        performed_by: str = 'system'
    ) -> Dict[str, Any]:
        """
        Sync pricing coefficients from Buz for an organization (synchronous).

        Note: For async operation, use the API endpoint which runs in background.

        Args:
            org_key: Organization key to sync
            include_inactive: Include inactive pricing
            performed_by: Who initiated the sync

        Returns:
            Dict with sync results
        """
        # Check for running sync
        running_syncs = self.db.get_running_syncs(org_key)
        if any(s['sync_type'] == 'pricing' for s in running_syncs):
            return {
                'success': False,
                'error': 'Pricing sync already in progress for this org'
            }

        # Start sync log and perform sync
        sync_id = self.db.start_sync(org_key, 'pricing')
        return self._do_pricing_sync(org_key, sync_id, include_inactive, performed_by)

    def sync_all(
        self,
        org_key: str,
        include_inactive: bool = True,
        performed_by: str = 'system'
    ) -> Dict[str, Any]:
        """
        Sync both inventory and pricing for an organization.

        Args:
            org_key: Organization key to sync
            include_inactive: Include inactive items/pricing
            performed_by: Who initiated the sync

        Returns:
            Dict with combined sync results
        """
        logger.info(f"Starting full sync for {org_key}")

        inventory_result = self.sync_inventory(org_key, include_inactive, performed_by)
        pricing_result = self.sync_pricing(org_key, include_inactive, performed_by)

        return {
            'success': inventory_result['success'] and pricing_result['success'],
            'org_key': org_key,
            'inventory': inventory_result,
            'pricing': pricing_result
        }

    def sync_all_orgs(
        self,
        include_inactive: bool = True,
        performed_by: str = 'system'
    ) -> Dict[str, Any]:
        """
        Sync all configured organizations.

        Args:
            include_inactive: Include inactive items/pricing
            performed_by: Who initiated the sync

        Returns:
            Dict with results for each org
        """
        results = {}
        for org_key in self.config.available_orgs:
            results[org_key] = self.sync_all(org_key, include_inactive, performed_by)

        success_count = sum(1 for r in results.values() if r['success'])
        return {
            'success': success_count == len(results),
            'orgs_synced': success_count,
            'orgs_total': len(results),
            'results': results
        }

    def get_sync_status(self, org_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current sync status.

        Args:
            org_key: Optional org filter

        Returns:
            Dict with sync status info
        """
        running = self.db.get_running_syncs(org_key)

        if org_key:
            last_inventory = self.db.get_last_sync(org_key, 'inventory')
            last_pricing = self.db.get_last_sync(org_key, 'pricing')

            return {
                'org_key': org_key,
                'is_syncing': len(running) > 0,
                'running_syncs': running,
                'last_inventory_sync': last_inventory,
                'last_pricing_sync': last_pricing
            }
        else:
            return {
                'is_syncing': len(running) > 0,
                'running_syncs': running,
                'available_orgs': self.config.available_orgs
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        db_stats = self.db.get_stats()
        return {
            **db_stats,
            'available_orgs': self.config.available_orgs,
            'missing_auth_orgs': list(self.config.buz_orgs_missing_auth.keys())
        }


# Create service instance (requires config, so initialized in app.py)
sync_service: Optional[SyncService] = None


def init_sync_service(config):
    """Initialize the sync service with config."""
    global sync_service
    sync_service = SyncService(config)
    return sync_service
