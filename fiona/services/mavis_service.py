"""
Mavis integration service for Fiona
Fetches Unleashed product data from Mavis
"""

import requests
import logging
from typing import List, Dict, Optional
from config import config

logger = logging.getLogger(__name__)


class MavisService:
    """Service for communicating with Mavis (Unleashed data bot)"""

    def __init__(self):
        self.timeout = 30

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Mavis API requests"""
        return {
            'X-API-Key': config.bot_api_key,
            'Content-Type': 'application/json'
        }

    def _get_url(self) -> str:
        """Get Mavis base URL"""
        return config.get_mavis_url()

    def get_product(self, code: str) -> Optional[Dict]:
        """
        Get a single product from Mavis by code.

        Returns None if not found or on error.
        """
        try:
            url = f"{self._get_url()}/api/products"
            response = requests.get(
                url,
                params={'code': code},
                headers=self._get_headers(),
                timeout=self.timeout
            )

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
            url = f"{self._get_url()}/api/products/bulk"
            response = requests.post(
                url,
                json={'codes': codes},
                headers=self._get_headers(),
                timeout=self.timeout
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Mavis returned status {response.status_code}: {response.text}")
                return {'products': [], 'not_found': codes}

        except requests.RequestException as e:
            logger.error(f"Failed to bulk fetch products from Mavis: {e}")
            return {'products': [], 'not_found': codes, 'error': str(e)}

    def get_all_fabric_products(self) -> List[Dict]:
        """
        Get all fabric products from Mavis.

        This fetches products that are in the fabric-related product groups.
        Note: This relies on Mavis having a product stats/list endpoint.
        For now, we'll use the products/stats endpoint to check connectivity.
        """
        try:
            # First check if Mavis is available
            url = f"{self._get_url()}/api/products/stats"
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=self.timeout
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Mavis returned status {response.status_code}")
                return {'error': f"Mavis returned status {response.status_code}"}

        except requests.RequestException as e:
            logger.error(f"Failed to connect to Mavis: {e}")
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
        try:
            url = f"{self._get_url()}/api/products/stats"
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=5
            )

            if response.status_code == 200:
                stats = response.json()
                return {
                    'connected': True,
                    'url': self._get_url(),
                    'product_count': stats.get('total_products', 0)
                }
            else:
                return {
                    'connected': False,
                    'url': self._get_url(),
                    'error': f"Status {response.status_code}"
                }

        except requests.RequestException as e:
            return {
                'connected': False,
                'url': self._get_url(),
                'error': str(e)
            }


# Global service instance
mavis_service = MavisService()
