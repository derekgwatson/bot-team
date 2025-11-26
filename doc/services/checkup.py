"""
Checkup service for Doc

Performs health checks ("welfare checks") on bots in the registry.
"""

import logging
import requests
import time
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import config
from database.db import db

logger = logging.getLogger(__name__)


class CheckupService:
    """Performs health checkups on bots"""

    def __init__(self):
        self.timeout = config.checkup_timeout
        self.batch_size = config.checkup_batch_size

    def check_bot(self, bot_name: str, bot_url: str = None) -> dict:
        """
        Perform a health check on a single bot.

        Args:
            bot_name: Name of the bot to check
            bot_url: Optional URL override. If not provided, looks up from DB.

        Returns:
            dict with check results
        """
        # Get bot info if URL not provided
        if not bot_url:
            bot = db.get_bot(bot_name)
            if not bot:
                return {
                    'bot_name': bot_name,
                    'status': 'unknown',
                    'error': f'Bot {bot_name} not found in registry'
                }
            bot_url = bot['url']

        health_url = f"{bot_url}/health"
        start_time = time.time()

        try:
            response = requests.get(health_url, timeout=self.timeout)
            elapsed_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                status = 'healthy'
            else:
                status = 'unhealthy'

            # Record the checkup
            db.record_checkup(
                bot_name=bot_name,
                status=status,
                response_time_ms=elapsed_ms,
                status_code=response.status_code
            )

            return {
                'bot_name': bot_name,
                'status': status,
                'response_time_ms': elapsed_ms,
                'status_code': response.status_code,
                'url': health_url
            }

        except requests.exceptions.ConnectionError:
            elapsed_ms = int((time.time() - start_time) * 1000)
            error = 'Connection refused'

            db.record_checkup(
                bot_name=bot_name,
                status='unreachable',
                response_time_ms=elapsed_ms,
                error_message=error
            )

            return {
                'bot_name': bot_name,
                'status': 'unreachable',
                'response_time_ms': elapsed_ms,
                'error': error,
                'url': health_url
            }

        except requests.exceptions.Timeout:
            elapsed_ms = int((time.time() - start_time) * 1000)
            error = f'Timeout after {self.timeout}s'

            db.record_checkup(
                bot_name=bot_name,
                status='timeout',
                response_time_ms=elapsed_ms,
                error_message=error
            )

            return {
                'bot_name': bot_name,
                'status': 'timeout',
                'response_time_ms': elapsed_ms,
                'error': error,
                'url': health_url
            }

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            error = str(e)

            db.record_checkup(
                bot_name=bot_name,
                status='error',
                response_time_ms=elapsed_ms,
                error_message=error
            )

            return {
                'bot_name': bot_name,
                'status': 'error',
                'response_time_ms': elapsed_ms,
                'error': error,
                'url': health_url
            }

    def check_all_bots(self) -> dict:
        """
        Perform health checks on all bots in the registry.

        Uses concurrent requests for efficiency.

        Returns:
            dict with overall results and per-bot results
        """
        bots = db.get_all_bots()

        if not bots:
            return {
                'success': True,
                'message': 'No bots in registry. Run a sync first.',
                'summary': {'total': 0, 'healthy': 0, 'unhealthy': 0},
                'results': []
            }

        results = []
        start_time = time.time()

        # Use ThreadPoolExecutor for concurrent checks
        with ThreadPoolExecutor(max_workers=self.batch_size) as executor:
            future_to_bot = {
                executor.submit(self.check_bot, bot['name'], bot['url']): bot
                for bot in bots
            }

            for future in as_completed(future_to_bot):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    bot = future_to_bot[future]
                    results.append({
                        'bot_name': bot['name'],
                        'status': 'error',
                        'error': str(e)
                    })

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Sort results by bot name for consistent ordering
        results.sort(key=lambda r: r['bot_name'])

        # Calculate summary
        healthy = sum(1 for r in results if r['status'] == 'healthy')
        total = len(results)

        return {
            'success': True,
            'total_time_ms': elapsed_ms,
            'summary': {
                'total': total,
                'healthy': healthy,
                'unhealthy': total - healthy
            },
            'results': results
        }

    def get_vitals(self, bot_name: str = None, hours: int = 24) -> dict:
        """
        Get vital statistics for a bot or the whole team.

        Args:
            bot_name: Optional bot name. If None, returns team vitals.
            hours: Number of hours to look back (default 24)

        Returns:
            dict with vital statistics
        """
        if bot_name:
            return db.get_bot_vitals(bot_name, hours)
        else:
            return db.get_team_vitals(hours)

    def get_latest_status(self) -> List[dict]:
        """
        Get the latest status for each bot.

        Returns:
            List of dicts with bot name and latest status
        """
        bots = db.get_all_bots()
        statuses = []

        for bot in bots:
            latest = db.get_latest_checkup(bot['name'])
            statuses.append({
                'bot_name': bot['name'],
                'description': bot.get('description', ''),
                'port': bot.get('port'),
                'status': latest['status'] if latest else 'unknown',
                'last_checked': latest['checked_at'] if latest else None,
                'response_time_ms': latest.get('response_time_ms') if latest else None
            })

        return statuses


# Singleton instance
checkup_service = CheckupService()
