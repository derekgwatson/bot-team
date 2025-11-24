"""
Sync Service

Handles synchronization of data from Unleashed to local database.
Tracks sync status and provides status reporting.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from database.db import db, utc_now_iso
from services.unleashed_client import UnleashedClient
from config import config

logger = logging.getLogger(__name__)


class SyncService:
    """
    Service for synchronizing Unleashed data to local database.

    Tracks sync status in memory and database.
    """

    def __init__(self):
        """Initialize the sync service"""
        self._lock = threading.Lock()
        self._status = {
            'status': 'idle',  # idle, running, success, failed
            'last_run_started_at': None,
            'last_run_finished_at': None,
            'last_successful_sync_at': None,
            'last_error': None,
            'current_sync_id': None
        }

        # Initialize last successful sync from database
        self._load_last_successful_sync()

    def _load_last_successful_sync(self):
        """Load last successful sync timestamp from database"""
        try:
            last_sync = db.get_last_successful_sync('products')
            if last_sync:
                self._status['last_successful_sync_at'] = last_sync.get('finished_at')
        except Exception as e:
            logger.warning(f"Could not load last successful sync: {e}")

    def _create_unleashed_client(self) -> UnleashedClient:
        """Create an Unleashed client with current config"""
        return UnleashedClient(
            api_id=config.unleashed_api_id,
            api_key=config.unleashed_api_key,
            base_url=config.unleashed_base_url,
            page_size=config.unleashed_page_size,
            timeout=config.unleashed_timeout
        )

    def get_status(self) -> Dict[str, Any]:
        """
        Get current sync status from database.

        Reads from database to ensure accuracy across workers/requests.
        """
        # Get the most recent sync record
        history = db.get_sync_history('products', limit=1)
        last_successful = db.get_last_successful_sync('products')

        if not history:
            return {
                'status': 'idle',
                'last_run_started_at': None,
                'last_run_finished_at': None,
                'last_successful_sync_at': None,
                'last_error': None
            }

        latest = history[0]
        status = latest.get('status', 'idle')

        # Map 'success'/'failed' to 'idle' for display if not running
        display_status = status if status == 'running' else status

        return {
            'status': display_status,
            'last_run_started_at': latest.get('started_at'),
            'last_run_finished_at': latest.get('finished_at'),
            'last_successful_sync_at': last_successful.get('finished_at') if last_successful else None,
            'last_error': latest.get('error_message') if status == 'failed' else None
        }

    def is_running(self) -> bool:
        """Check if a sync is currently running (database-based for multi-worker)"""
        return db.is_sync_running('products')

    def _extract_product_data(self, unleashed_product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant fields from an Unleashed product response.

        Maps Unleashed field names to our normalized schema.
        """
        # Extract sell price from tier 9 if available
        sell_price_tier_9 = None
        sell_price_tiers = unleashed_product.get('SellPriceTiers', [])
        if sell_price_tiers:
            for tier in sell_price_tiers:
                if tier.get('Name') == 'Tier 9' or tier.get('Level') == 9:
                    sell_price_tier_9 = tier.get('Value')
                    break

        # Extract product group/subgroup
        product_group = unleashed_product.get('ProductGroup', {})
        group_name = product_group.get('GroupName', '') if product_group else ''

        return {
            'product_code': unleashed_product.get('ProductCode', ''),
            'product_description': unleashed_product.get('ProductDescription', ''),
            'product_group': group_name,
            'default_sell_price': unleashed_product.get('DefaultSellPrice'),
            'sell_price_tier_9': sell_price_tier_9,
            'unit_of_measure': unleashed_product.get('UnitOfMeasure', {}).get('Name', ''),
            'width': unleashed_product.get('Width'),
            'is_sellable': unleashed_product.get('IsSellable', True),
            'is_obsolete': unleashed_product.get('IsObsolete', False),
            'raw_payload': json.dumps(unleashed_product)
        }

    def run_product_sync(self) -> Dict[str, Any]:
        """
        Run a full product sync from Unleashed.

        Returns dict with sync results.
        """
        # Check if already running (database-based lock for multi-worker support)
        if db.is_sync_running('products'):
            return {
                'success': False,
                'error': 'Sync already in progress',
                'status': self.get_status()
            }

        # Create sync record in database (this is our lock)
        sync_id = db.create_sync_record('products')

        with self._lock:
            self._status['status'] = 'running'
            self._status['last_run_started_at'] = utc_now_iso()
            self._status['last_error'] = None
            self._status['current_sync_id'] = sync_id

        records_processed = 0
        records_created = 0
        records_updated = 0

        try:
            # Create client and fetch products with progress updates
            client = self._create_unleashed_client()

            # Progress callback to update UI during fetch phase
            def on_fetch_progress(fetched_count):
                db.update_sync_progress(
                    sync_id,
                    records_processed=fetched_count,
                    records_created=0,
                    records_updated=0
                )

            products = client.fetch_all_products(progress_callback=on_fetch_progress)

            logger.info(f"Fetched {len(products)} products from Unleashed, starting sync")

            # Process each product (update progress every 100 records)
            progress_interval = 100
            for product in products:
                try:
                    product_data = self._extract_product_data(product)
                    product_id, was_created = db.upsert_product(product_data)

                    records_processed += 1
                    if was_created:
                        records_created += 1
                    else:
                        records_updated += 1

                    # Update progress periodically so UI can show live updates
                    if records_processed % progress_interval == 0:
                        logger.info(f"Sync progress: {records_processed} processed, {records_created} created, {records_updated} updated")
                        db.update_sync_progress(
                            sync_id,
                            records_processed=records_processed,
                            records_created=records_created,
                            records_updated=records_updated
                        )

                except Exception as e:
                    logger.error(
                        f"Error processing product {product.get('ProductCode', 'unknown')}: {e}"
                    )
                    # Continue processing other products

            # Mark sync as successful
            finished_at = utc_now_iso()
            db.update_sync_record(
                sync_id,
                status='success',
                records_processed=records_processed,
                records_created=records_created,
                records_updated=records_updated
            )

            with self._lock:
                self._status['status'] = 'success'
                self._status['last_run_finished_at'] = finished_at
                self._status['last_successful_sync_at'] = finished_at
                self._status['current_sync_id'] = None

            logger.info(
                f"Product sync completed: {records_processed} processed, "
                f"{records_created} created, {records_updated} updated"
            )

            return {
                'success': True,
                'records_processed': records_processed,
                'records_created': records_created,
                'records_updated': records_updated,
                'started_at': self._status['last_run_started_at'],
                'finished_at': finished_at
            }

        except Exception as e:
            error_message = str(e)
            logger.exception(f"Product sync failed: {error_message}")

            # Mark sync as failed
            finished_at = utc_now_iso()
            db.update_sync_record(
                sync_id,
                status='failed',
                records_processed=records_processed,
                records_created=records_created,
                records_updated=records_updated,
                error_message=error_message
            )

            with self._lock:
                self._status['status'] = 'failed'
                self._status['last_run_finished_at'] = finished_at
                self._status['last_error'] = error_message
                self._status['current_sync_id'] = None

            return {
                'success': False,
                'error': error_message,
                'records_processed': records_processed,
                'records_created': records_created,
                'records_updated': records_updated,
                'started_at': self._status['last_run_started_at'],
                'finished_at': finished_at
            }

    def get_sync_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent sync history from database"""
        return db.get_sync_history('products', limit)


# Global sync service instance
sync_service = SyncService()
