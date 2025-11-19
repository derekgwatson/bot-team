"""Bot team service - handles health checks and bot information."""
import requests
from typing import Dict, List, Optional
from chester.config import config
from chester.services.database import Database


class BotService:
    """Service for managing bot team information and health checks."""

    def __init__(self):
        self.timeout = config.health_check_timeout
        self.db = Database()

    def get_all_bots(self) -> Dict:
        """Get information about all bots in the team."""
        return config.bot_team

    def get_bot_info(self, bot_name: str) -> Optional[Dict]:
        """Get information about a specific bot."""
        return config.bot_team.get(bot_name)

    def _build_health_url(self, bot_name: str) -> Optional[str]:
        """
        Build health check URL for a bot from database configuration.

        For bots with skip_nginx=True (Sally): http://localhost:{port}/health
        For all other bots: https://{domain}/health

        Returns:
            Health check URL, or None if bot not found in database
        """
        bot_config = self.db.get_bot(bot_name)
        if not bot_config:
            return None

        if bot_config.get('skip_nginx'):
            # Sally uses localhost
            port = bot_config.get('port', 8004)
            return f"http://localhost:{port}/health"
        else:
            # Production bots use their domain
            domain = bot_config.get('domain')
            return f"https://{domain}/health"

    def check_bot_health(self, bot_name: str) -> Dict:
        """
        Check the health of a specific bot.

        Returns:
            Dict with status, response_time, and any error information
        """
        bot_info = self.get_bot_info(bot_name)
        if not bot_info:
            return {
                'bot': bot_name,
                'status': 'unknown',
                'error': 'Bot not found in registry'
            }

        health_url = self._build_health_url(bot_name)
        if not health_url:
            return {
                'bot': bot_name,
                'status': 'unknown',
                'error': 'Bot configuration not found in database'
            }

        try:
            response = requests.get(health_url, timeout=self.timeout)
            return {
                'bot': bot_name,
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'url': health_url
            }
        except requests.exceptions.Timeout:
            return {
                'bot': bot_name,
                'status': 'timeout',
                'error': f'Health check timed out after {self.timeout} seconds',
                'url': health_url
            }
        except requests.exceptions.ConnectionError:
            return {
                'bot': bot_name,
                'status': 'unreachable',
                'error': 'Could not connect to bot',
                'url': health_url
            }
        except Exception as e:
            return {
                'bot': bot_name,
                'status': 'error',
                'error': str(e),
                'url': health_url
            }

    def check_all_bots_health(self) -> List[Dict]:
        """
        Check the health of all bots in the team.

        Returns:
            List of health check results for each bot
        """
        results = []
        for bot_name in config.bot_team.keys():
            health = self.check_bot_health(bot_name)
            results.append(health)
        return results

    def get_bot_capabilities(self, bot_name: str) -> Optional[List[str]]:
        """Get the capabilities of a specific bot."""
        bot_info = self.get_bot_info(bot_name)
        if bot_info:
            return bot_info.get('capabilities', [])
        return None

    def search_bots_by_capability(self, keyword: str) -> List[Dict]:
        """
        Search for bots that have capabilities matching a keyword.

        Args:
            keyword: Search term to match against capabilities

        Returns:
            List of bots with matching capabilities
        """
        results = []
        keyword_lower = keyword.lower()

        for bot_name, bot_info in config.bot_team.items():
            capabilities = bot_info.get('capabilities', [])
            matching_capabilities = [
                cap for cap in capabilities
                if keyword_lower in cap.lower()
            ]

            if matching_capabilities:
                # Get domain from database for the bot's URL
                bot_config = self.db.get_bot(bot_name)
                bot_url = f"https://{bot_config['domain']}" if bot_config else 'Unknown'

                results.append({
                    'bot': bot_name,
                    'name': bot_info['name'],
                    'description': bot_info['description'],
                    'matching_capabilities': matching_capabilities,
                    'url': bot_url
                })

        return results

    def get_team_summary(self) -> Dict:
        """Get a summary of the entire bot team."""
        bots = config.bot_team
        return {
            'total_bots': len(bots),
            'bot_names': [info['name'] for info in bots.values()],
            'bots': bots
        }


# Global bot service instance
bot_service = BotService()
