"""
Sync service for Doc

Syncs the bot registry from Chester into Doc's local database.
This allows Doc to operate independently even when Chester is unavailable.
"""

import logging
import requests
from typing import Optional

from config import config
from database.db import db
from shared.http_client import BotHttpClient

logger = logging.getLogger(__name__)


class SyncService:
    """Handles syncing bot registry from Chester"""

    def __init__(self):
        self.timeout = 10  # seconds

    def sync_from_chester(self) -> dict:
        """
        Sync the bot registry from Chester.

        Returns a dict with sync results:
        {
            'success': bool,
            'bots_synced': int,
            'error': str (if failed)
        }
        """
        chester_url = config.get_chester_url()
        logger.info(f"Syncing bot registry from Chester at {chester_url}")

        try:
            # Call Chester's /api/bots endpoint
            chester = BotHttpClient(chester_url, timeout=self.timeout)
            response = chester.get('/api/bots')
            response.raise_for_status()

            data = response.json()
            if not data.get('success'):
                error = data.get('error', 'Unknown error from Chester')
                logger.error(f"Chester returned error: {error}")
                return {'success': False, 'bots_synced': 0, 'error': error}

            bots = data.get('bots', {})
            synced_count = 0

            # Chester returns bots as a dict keyed by bot name
            for bot_name, bot_info in bots.items():
                # Skip Doc itself - we don't need to health check ourselves
                if bot_name == 'doc':
                    continue

                port = bot_info.get('port', 0)
                description = bot_info.get('description', '')
                capabilities = bot_info.get('capabilities', [])

                # Build URL based on environment
                if config.is_dev_mode():
                    url = f"http://localhost:{port}"
                else:
                    # In prod, we'd use the domain - for now use localhost
                    # This could be enhanced to get actual URLs from Chester
                    url = f"http://localhost:{port}"

                db.upsert_bot(
                    name=bot_name,
                    port=port,
                    url=url,
                    description=description,
                    capabilities=capabilities
                )
                synced_count += 1

            logger.info(f"Successfully synced {synced_count} bots from Chester")
            return {'success': True, 'bots_synced': synced_count, 'error': None}

        except requests.exceptions.ConnectionError:
            error = f"Could not connect to Chester at {chester_url}"
            logger.warning(error)
            return {'success': False, 'bots_synced': 0, 'error': error}

        except requests.exceptions.Timeout:
            error = f"Timeout connecting to Chester at {chester_url}"
            logger.warning(error)
            return {'success': False, 'bots_synced': 0, 'error': error}

        except requests.exceptions.RequestException as e:
            error = f"Request error syncing from Chester: {str(e)}"
            logger.error(error)
            return {'success': False, 'bots_synced': 0, 'error': error}

        except Exception as e:
            error = f"Unexpected error syncing from Chester: {str(e)}"
            logger.exception(error)
            return {'success': False, 'bots_synced': 0, 'error': error}

    def get_sync_status(self) -> dict:
        """Get the current sync status"""
        bots = db.get_all_bots()
        bot_count = len(bots)

        # Find the most recent sync time
        last_sync = None
        for bot in bots:
            sync_time = bot.get('last_synced_at')
            if sync_time and (last_sync is None or sync_time > last_sync):
                last_sync = sync_time

        return {
            'bot_count': bot_count,
            'last_sync': last_sync,
            'chester_url': config.get_chester_url()
        }


# Singleton instance
sync_service = SyncService()
