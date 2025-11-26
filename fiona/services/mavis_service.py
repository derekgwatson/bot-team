"""
Mavis integration service for Fiona
Fetches Unleashed product data from Mavis
"""

import requests
import logging
from typing import List, Dict, Optional
from config import config
from shared.http_client import BotHttpClient

logger = logging.getLogger(__name__)


class MavisService:
    """Service for communicating with Mavis (Unleashed data bot)"""

    def __init__(self):
        self.timeout = 30

    def _get_client(self, timeout: int = None) -> BotHttpClient:
        """Get a BotHttpClient for Mavis"""
        return BotHttpClient(config.get_mavis_url(), timeout=timeout or self.timeout)

    def get_product(self, code: str) -> Optional[Dict]:
        """
        Get a single product from Mavis by code.

        Returns None if not found or on error.
        """
        try:
            client = self._get_client()
            response = client.get('/api/products', params={'code': code})

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None
            else:
                logger.error(f"Mavis returned status {response.status_code}: {response.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"Failed to fetch product from Mavis: {e}")
            return None

    def get_products_bulk(self, codes: List[str]) -> Dict:
        """
        Bulk lookup products from Mavis.

        Returns:
            {
                'products': [...],
                'not_found': [...]
            }
        """
        try:
            client = self._get_client()
            response = client.post('/api/products/bulk', json={'codes': codes})

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Mavis returned status {response.status_code}: {response.text}")
                return {'products': [], 'not_found': codes}

        except requests.RequestException as e:
            logger.error(f"Failed to bulk fetch products from Mavis: {e}")
            return {'products': [], 'not_found': codes, 'error': str(e)}

    def get_valid_fabric_codes(self) -> Dict:
        """
        Get all valid fabric product codes from Mavis.

        Valid fabrics are products where:
        - product_group starts with 'Fabric'
        - is_obsolete = false
        - is_sellable = true

        Returns:
            {'codes': [...], 'count': int} or {'error': str}
        """
        try:
            client = self._get_client()
            response = client.get('/api/products/fabrics', params={'codes_only': 'true'})

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Mavis returned status {response.status_code}: {response.text}")
                return {'error': f"Mavis returned status {response.status_code}"}

        except requests.RequestException as e:
            logger.error(f"Failed to get fabric codes from Mavis: {e}")
            return {'error': str(e)}

    def get_valid_fabric_products(self) -> Dict:
        """
        Get all valid fabric products with full details from Mavis.

        Returns:
            {'products': [...], 'count': int} or {'error': str}
        """
        try:
            client = self._get_client()
            response = client.get('/api/products/fabrics')

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Mavis returned status {response.status_code}: {response.text}")
                return {'error': f"Mavis returned status {response.status_code}"}

        except requests.RequestException as e:
            logger.error(f"Failed to get fabric products from Mavis: {e}")
            return {'error': str(e)}

    def check_connection(self) -> Dict:
        """
        Check if Mavis is available.

        Returns:
            {
                'connected': bool,
                'url': str,
                'product_count': int (if connected),
                'error': str (if not connected)
            }
        """
        mavis_url = config.get_mavis_url()
        try:
            client = self._get_client(timeout=5)
            response = client.get('/api/products/stats')

            if response.status_code == 200:
                stats = response.json()
                return {
                    'connected': True,
                    'url': mavis_url,
                    'product_count': stats.get('total_products', 0)
                }
            else:
                return {
                    'connected': False,
                    'url': mavis_url,
                    'error': f"Status {response.status_code}"
                }

        except requests.RequestException as e:
            return {
                'connected': False,
                'url': mavis_url,
                'error': str(e)
            }


# Global service instance
mavis_service = MavisService()
